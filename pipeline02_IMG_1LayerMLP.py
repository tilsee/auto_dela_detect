import yaml
import json
import os
import glob
import shutil
import pandas as pd
import numpy as np
import cv2
import matplotlib.pyplot as plt
from matplotlib import transforms
import scipy
import inspect
import tensorflow as tf

from sklearn.metrics import confusion_matrix
from sklearn.model_selection import train_test_split


plt.rcParams['image.cmap'] = 'gray'


class pipe_deladetect():
    def __init__(self):
        # stores preset parameters
        self.config = None
        self.srcpath = None
        self.dstpath = None
        self.configpath = 'configs/pipeline02config.yaml'

        # keeping track of which processes were already run
        self.status = {}

        # buffers 
        self.raw_image_list = None
        self.currentimagenr = 0
        self.latestimage = None
        self.latestlabel = None
        self.imgrgb = None
        self.imgcrop = None
        # results
        self.eval = None
        
    def load_new_image(self, imgpath):
        latestimage = cv2.imread(imgpath)
        self.latestimage = cv2.cvtColor(latestimage, cv2.COLOR_BGR2GRAY)
        self.imgrgb = cv2.cvtColor(latestimage, cv2.COLOR_BGR2RGB)
        self.ydat.append(self.labelconvdict[imgpath.split("/")[-2]])
    
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
        # splits all data randomly into a training and test set while maintaining a 50/50 label split in each
        data_dir = self.srcpath
        split_dir = self.dstpath+"/traindat"
        val_pct = 0.2
        test_pct = 0.2
        class_dirs = os.listdir(data_dir)
        for class_dir in class_dirs:
            class_path = os.path.join(data_dir, class_dir)
            image_filenames = os.listdir(class_path)
            image_paths = [os.path.join(class_path, fn) for fn in image_filenames]
            train_paths, val_test_paths = train_test_split(image_paths, test_size=val_pct+test_pct, random_state=23030612)
            val_paths, test_paths = train_test_split(val_test_paths, test_size=test_pct/(val_pct+test_pct), random_state=23030612)
            train_dir = os.path.join(split_dir, 'train', class_dir)
            val_dir = os.path.join(split_dir, 'val', class_dir)
            test_dir = os.path.join(split_dir, 'test', class_dir)
            self.clean_dir(train_dir)
            self.clean_dir(val_dir)
            self.clean_dir(test_dir)
            for path in train_paths:
                shutil.copy(path, train_dir)
            for path in val_paths:
                shutil.copy(path, val_dir)
            for path in test_paths:
                shutil.copy(path, test_dir)
            self.srcpath = split_dir
        self.config["General"]["conversionstat"] = True
        self.config["Paths"]["srcpath"] = split_dir
        with open(self.configpath, 'w') as outfile:
            yaml.dump(self.config, outfile, default_flow_style=False)

    def create_ds(self):
        # Set the image dimensions
        with tf.keras.preprocessing.image.load_img(self.get_imagepaths(rootpath="dst/2302_pez_tfds/traindat/train")[0]) as img:
            self.image_size = (img.height, img.width)
        # Create the datasets for the training, validation, and test sets
        batchsize = self.config["Hyperparameters"]["batch_size"]
        self.classnames=["normal","delam"]


        ds_train=tf.keras.utils.image_dataset_from_directory(
        self.srcpath+"/train/",
        color_mode = "grayscale",
        labels= "inferred",
        class_names=self.classnames,
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

        ds_test =tf.keras.utils.image_dataset_from_directory(
        self.srcpath+"/test/",
        color_mode = "grayscale",
        class_names=self.classnames,
        labels= "inferred",
        image_size=self.image_size,
        batch_size=batchsize,
        shuffle=False)
        self.ds_test = ds_test.map(lambda x, y: (x / 255.0, y))

    def create_model(self):
        optimizer = self.config["Hyperparameters"]["optimizer"]
        neurons = self.config["Hyperparameters"]["neurons"]
        lr_adam = self.config["Hyperparameters"]["lr_adam"]
        lr_sdg = self.config["Hyperparameters"]["lr_sdg"]

        self.model = tf.keras.models.Sequential([
        tf.keras.layers.Flatten(input_shape=self.image_size),  # Flatten the input image
        tf.keras.layers.Dense(neurons, activation='relu'),  # Hidden layer with 128 neurons and ReLU activation
        tf.keras.layers.Dense(1, activation='sigmoid')  # Output layer with 1 neuron and sigmoid activation
        ])

        lossfunctsdict={
            "binary_crossentropy": tf.keras.losses.BinaryCrossentropy(from_logits=self.config["Hyperparameters"]["from_logits"]),
        }
        optimizerdict={
            "adam" : tf.keras.optimizers.Adam(learning_rate=lr_adam),
            "sdg": tf.keras.optimizers.SGD(learning_rate=lr_sdg)
            }
        self.model.compile(optimizer=optimizerdict[optimizer], loss=lossfunctsdict["binary_crossentropy"], metrics=['accuracy'])
    
    def trainmodel(self):
        #cb_cheackpoint = tf.keras.callbacks.ModelCheckpoint(self.srcpath+"pipeline02model.h5, save_best_only=True")
        cb_earlystop= tf.keras.callbacks.EarlyStopping(
                monitor='val_loss',
                patience= 10,
                restore_best_weights=True,
                start_from_epoch=5
            )
        cb_checkpoint = tf.keras.callbacks.ModelCheckpoint(
                self.srcpath+"/model/pipeline02-{epoch:02d}-{val_loss:.2f}-{val_accuracy:.2f}.hdf5",
                save_best_only= True)
        epochs = self.config["Hyperparameters"]["epochs"]
        self.history = self.model.fit(self.ds_train,validation_data=self.ds_val ,epochs = epochs, verbose = 1, callbacks=[cb_earlystop, cb_checkpoint])

    def run_pipeline(self):
        self.load_setup()
        if self.config["General"]["conversionstat"] == False:
            print("hello")
            self.get_imagepaths()
            self.convert_csv2png()
            self.trainvaltestsplit()
        self.create_ds()
        self.create_model()
        self.trainmodel()
        self.gen_confmatrix()
        #self.gen_confmatrix()

    def gen_confmatrix(self):
        y_pred = self.model.predict(self.ds_test)
        y_pred_classes = y_pred.round().astype("int")
        y_true_classes = np.concatenate([y for x, y in self.ds_test], axis=0)
        conf_matrix = confusion_matrix(y_true_classes, y_pred.round().astype("int"))
        self.acc= (conf_matrix[1][1]+conf_matrix[0][0])/len(y_pred_classes)

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
        print("Acc: " + str(self.acc))


if __name__ == "__main__":
    new_pipeline = pipe_deladetect()
    new_pipeline.run_pipeline()