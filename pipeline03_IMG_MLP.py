import yaml
import os
import glob
import shutil
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import tensorflow as tf
import optuna
from sklearn.metrics import confusion_matrix ,roc_auc_score, roc_curve, precision_recall_curve, det_curve
from sklearn.model_selection import train_test_split

plt.rcParams['image.cmap'] = 'gray'


class pipe_deladetect():
    def __init__(self, trial=None):
        # stores preset parameters
        self.config = None
        self.srcpath = None
        self.dstpath = None
        self.configpath = 'configs/pipeline03config.yaml'
        self.trial = trial
        self.callbackslst=[]

        # buffers 
        self.raw_image_list = None
        self.currentimagenr = 0
        self.latestimage = None
        self.latestlabel = None
        self.imgrgb = None
        self.imgcrop = None
        # results
        self.eval = None
        self.finalmetrics = {}
            
    def crop_img(self):
        bottom = self.config["Cropping"]["bottom"]
        left = self.config["Cropping"]["left"]
        right = self.config["Cropping"]["right"]
        top = self.config["Cropping"]["top"]
        hight,width = self.latestimage.shape
        self.hight=hight-bottom-top
        self.width=width-left-right

        croppedimg = self.latestimage[top:hight-bottom, left:width-right]
        self.latestimage = self.imgcrop = croppedimg

    def convert_csv2png(self):
        convdstpath = f"{self.dstpath}/png/"
        self.get_imagepaths(fending="Data.csv")
        self.clean_dir(convdstpath)
        recursive = True
        for imgpath in self.raw_image_list:
            img=pd.read_csv(imgpath).to_numpy()
            self.latestimage=img
            self.crop_img()
            if recursive:
                folders=imgpath.split("/")
                for folder in self.srcpath.split("/"):
                    folders.remove(folder)
                folders.pop()
                if folders != []:
                    savepath = convdstpath + "/".join(folders)
                else: 
                    savepath = convdstpath
                    recursive = False
            fname= self.gen_filename(savepath,"ImagePData")
            if not os.path.exists("/".join(fname.split("/")[:-1])) :
                self.clean_dir("/".join(fname.split("/")[:-1]))
            _=plt.imsave(fname,self.latestimage)
        self.srcpath = self.dstpath+"/png"
        self.get_imagepaths()

    def load_setup(self): # loads config from config.yaml
        with open(self.configpath, 'r') as file:
            self.config = yaml.safe_load(file)
        self.srcpath = self.config["Paths"]["srcpath"]
        self.dstpath = self.config["Paths"]["dstpath"]
    
    def get_imagepaths(self,fending=".png", rootpath = None): # loads source images
        if rootpath == None: rootpath = self.srcpath
        image_list = glob.glob(f"{rootpath}/*/*{fending}", recursive=True)
        if image_list == []:
            image_list = glob.glob(f"{rootpath}/*{fending}", recursive=True)
        image_list.sort()
        self.raw_image_list = image_list
        return image_list
    
    def gen_filename(self, path2folder, filename):
        i = 1
        try:
            while os.path.exists(f"{path2folder}/{filename}{i:03d}.png"):
                i += 1
        except: pass
        return f"{path2folder}/{filename}{i:03d}.png"

    def clean_dir(self,path):
        try:
            shutil.rmtree(path)
        except: pass
        os.makedirs(path)

    def trainvaltestsplit(self):
        data_dir = self.srcpath
        split_dir = self.dstpath+"/traindat"
        val_pct = 0.3
        class_dirs = os.listdir(data_dir)
        for class_dir in class_dirs:
            class_path = os.path.join(data_dir, class_dir)
            image_filenames = os.listdir(class_path)
            image_paths = [os.path.join(class_path, fn) for fn in image_filenames]
            train_paths, val_paths = train_test_split(image_paths, test_size=val_pct, random_state=23030712)
            train_dir = os.path.join(split_dir, 'train', class_dir)
            val_dir = os.path.join(split_dir, 'val', class_dir)
            self.clean_dir(train_dir)
            self.clean_dir(val_dir)
            for path in train_paths:
                shutil.copy(path, train_dir)
            for path in val_paths:
                shutil.copy(path, val_dir)
            self.srcpath = split_dir
        self.config["General"]["conversionstat"] = True
        self.config["Paths"]["srcpath"] = split_dir
        with open(self.configpath, 'w') as outfile:
            yaml.dump(self.config, outfile, default_flow_style=False)

    def create_ds(self):
        # Set the image dimensions
        with tf.keras.preprocessing.image.load_img(self.get_imagepaths(rootpath="dst/2303_pez_dnn/traindat/train")[0]) as img:
            self.image_size = (img.height, img.width)
        # Create the datasets for the training, validation, and test sets
        batchsize = self.config["Hyperparameters"]["batch_size"]
        self.classnames=["normal","delam"]

        ds_train=tf.keras.utils.image_dataset_from_directory(
        self.srcpath+"/train/",
        color_mode = "grayscale",
        class_names=self.classnames,
        labels= "inferred",
        seed=230305,
        image_size=self.image_size,
        batch_size=batchsize)
        self.ds_train = ds_train.map(lambda x, y: (x / 255.0, y))

        ds_val =tf.keras.utils.image_dataset_from_directory(
        self.srcpath+"/val/",
        color_mode = "grayscale",
        class_names=self.classnames,
        labels= "inferred",
        image_size=self.image_size,
        batch_size=batchsize,
        shuffle=False)
        self.ds_val = ds_val.map(lambda x, y: (x / 255.0, y))

    def create_model(self):
        optimizer = self.config["Hyperparameters"]["optimizer"]
        neurons = self.config["Hyperparameters"]["neurons"]
        layers = self.config["Hyperparameters"]["layers"]        
        lr_adam = self.config["Hyperparameters"]["lr_adam"]

        """         self.model = tf.keras.models.Sequential([
        tf.keras.layers.Flatten(input_shape=self.image_size),  # Flatten the input image
        tf.keras.layers.Dense(neurons, activation='relu'),  # Hidden layer with 128 neurons and ReLU activation
        tf.keras.layers.Dense(1, activation='sigmoid')  # Output layer with 1 neuron and sigmoid activation
        ]) """

        inputs = tf.keras.layers.Input(shape=self.image_size)
        x = tf.keras.layers.Flatten()(inputs)
        x =  tf.keras.layers.Dense(neurons, activation='relu')(x)
        for i in range(layers):
            x =  tf.keras.layers.Dense(neurons, activation='relu')(x)
        outputs = tf.keras.layers.Dense(1, activation='sigmoid')(x)
        self.model = tf.keras.Model(inputs=inputs, outputs=outputs)

        lossfunctsdict={
            "binary_crossentropy": tf.keras.losses.BinaryCrossentropy(),
        }
        optimizerdict={
            "adam" : tf.keras.optimizers.Adam(learning_rate=lr_adam),
            }
        self.model.compile(optimizer=optimizerdict[optimizer], loss=lossfunctsdict["binary_crossentropy"], metrics=['accuracy'])
    
    def trainmodel(self):
        print(self.config["Hyperparameters"])
        cb_earlystop= tf.keras.callbacks.EarlyStopping(
                monitor='val_loss',
                patience= 5,
                restore_best_weights=True,
                start_from_epoch=5
                )
        self.callbackslst.append(cb_earlystop)

        #cb_checkpoint = tf.keras.callbacks.ModelCheckpoint(
        #        self.srcpath+"/model/epoche_{epoch:02d}-acc_{val_accuracy:.2f}-loss_{val_loss:.2f}.hdf5",
        #        save_best_only= True)
        # if self.trial ==  None: self.callbackslst.append(cb_checkpoint)

        optuna_lambda =  tf.keras.callbacks.LambdaCallback(
            on_epoch_end= lambda epoch, logs: self.pruning(epoch,logs)
        )
        if self.trial != None: self.callbackslst.append(optuna_lambda)

        epochs = self.config["Hyperparameters"]["epochs"]
        self.history = self.model.fit(self.ds_train,validation_data=self.ds_val ,epochs = epochs, verbose = 1, callbacks=self.callbackslst)

    def pruning(self, step, logs):
        objectiveval=logs["val_loss"]
        self.trial.report(objectiveval, step)
        if self.trial.should_prune():
            raise optuna.TrialPruned()            

    def run_pipeline(self):
        self.load_setup()
        if self.config["General"]["conversionstat"] == False:
            self.get_imagepaths(fending="Data.csv")
            self.convert_csv2png()
            self.trainvaltestsplit()
        self.create_ds()
        self.create_model()
        self.trainmodel()
        self.performanc_analyser()

    def performanc_analyser(self):
        ds = self.ds_val

        self.loss, self.acc = self.model.evaluate(self.ds_val)

        y_pred = self.model.predict(ds)
        y_pred_classes = y_pred.round().astype("int")
        y_true_classes = np.concatenate([y for x, y in ds], axis=0)

        # ge condusion matrix
        conf_matrix = confusion_matrix(y_true_classes, y_pred.round().astype("int"))
        fig, ax = plt.subplots(figsize=(7.5, 7.5))
        ax.matshow(conf_matrix, cmap=plt.cm.Blues, alpha=0.3)
        for i in range(len(conf_matrix)):
            for j in range(len(conf_matrix[1])):
                ax.text(x=j, y=i,s=conf_matrix[i][j], va='center', ha='center', size='xx-large')
        plt.xlabel('Predictions', fontsize=18)
        plt.ylabel('Actuals', fontsize=18)
        plt.title(f'Confusion Matrix', fontsize=18)
        plt.figtext(0, 0, f'Dataset Size: {len(y_pred_classes)}\nSample Split: {sum(conf_matrix[0]/sum(conf_matrix[1]))}\nAcc: {self.acc}\nOptimizer: {self.config["Hyperparameters"]["optimizer"]}')
        fig.savefig(self.dstpath+"/confusion")
        plt.close("all")        
        
        # calculating precision, recall and f1 score
        tn, fp, fn, tp = conf_matrix.ravel()
        self.precision=tp/(tp+fp)
        self.recall=tp/(tp+fn)
        self.f1=tp/(tp+(fn+fp)/2)

        #ploting precision recall curve
        precisions, recalls, thresholds = precision_recall_curve(y_true_classes,y_pred)
        plt.plot(recalls, precisions) 
        plt.xlabel('Recall', fontsize=18)
        plt.ylabel('Precision', fontsize=18)
        plt.title(f'Precision-Recall (PR) Curve', fontsize=18)
        plt.savefig(self.dstpath+"/prereccurve")
        plt.close("all")

        # plotting roc curve
        fpr, tpr, thresholds = roc_curve(y_true_classes,y_pred)
        plt.plot(fpr, tpr) 
        plt.xlabel('False Positiv Rate', fontsize=18)
        plt.ylabel('True Positive Rate', fontsize=18)
        plt.title(f'Receiver Operating Characteristic (ROC) Curve', fontsize=18)
        plt.savefig(self.dstpath+"/roccurve")
        plt.close("all")  

        # plotting det curve
        fpr, fnr, thresholds = det_curve(y_true_classes, y_pred)
        plt.plot(fpr, fnr) 
        plt.xlabel('False Positiv Rate', fontsize=18)
        plt.ylabel('False Negative Rate', fontsize=18)
        plt.title(f'Detection Error Tradeoff (DET) Curve', fontsize=18)
        plt.ylim([0,1])
        plt.xlim([0,1])
        plt.savefig(self.dstpath+"/detcurve")
        plt.close("all")

        self.finalmetrics = {
            "final_loss": self.loss,
            "final_acc": self.acc,
            "tp": tp,
            "fp": fp,
            "tn": tn,
            "fn": fn,
            "f1": self.f1,
            "roc_auc": roc_auc_score(y_true=y_true_classes, y_score=y_pred)
        }
        print("Final val_acc: " + str(self.acc))


if __name__ == "__main__":
    new_pipeline = pipe_deladetect()
    new_pipeline.run_pipeline()
