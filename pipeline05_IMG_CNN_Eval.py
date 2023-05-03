import tensorflow as tf
from tensorflow import keras
from keras import datasets, layers, models
import matplotlib.pyplot as plt
import os
import Scripts.dsutils as dsutils
from sklearn.metrics import confusion_matrix ,roc_auc_score, roc_curve, precision_recall_curve, det_curve
import numpy as np
import json
import glob
import cv2

def load_ds(srcpath, batch_size, image_size):

    #load data into train and val dataset
    ds_train, ds_val=tf.keras.utils.image_dataset_from_directory(
    directory=srcpath,
    validation_split=0.3,
    subset="both",
    color_mode = "grayscale",
    label_mode="int",
    class_names= ['nodefect', 'defect'],
    labels= "inferred",
    seed=230421,
    image_size= image_size,
    batch_size=batch_size)
    ds_train = ds_train.map(lambda x, y: (x / 255.0, y))
    ds_val = ds_val.map(lambda x, y: (x / 255.0, y))
    return ds_train, ds_val

def load_evalds(srcpath, batch_size, image_size):

    #load data into train and val dataset
    ds_eval=tf.keras.utils.image_dataset_from_directory(
    directory=srcpath,
    color_mode = "grayscale",
    label_mode="int",
    class_names= ['nodefect', 'defect'],
    labels= "inferred",
    image_size= image_size,
    batch_size=batch_size,
    shuffle=False)
    ds_eval = ds_eval.map(lambda x, y: (x / 255.0, y))
    return ds_eval

def create_model(input_size, cnnlyrs, initialfilternr, dropout, normalization):
    multi=0
    #input layer
    model = models.Sequential()
    model.add(layers.Conv2D(initialfilternr, 7, activation='relu', input_shape=(input_size[0], input_size[1], 1)))
    model.add(layers.MaxPooling2D(2))
    if normalization:
        model.add(layers.BatchNormalization())
    for _ in range(cnnlyrs):
        nrfilters=int(2**multi*initialfilternr)
        model.add(layers.Conv2D(nrfilters, 3, activation='relu'))
        model.add(layers.Conv2D(nrfilters, 3, activation='relu'))
        model.add(layers.MaxPooling2D(2))
        if normalization:
            model.add(layers.BatchNormalization())
        multi+=1
    model.add(layers.Flatten())
    model.add(layers.Dense(128, activation='relu'))
    if dropout:
        model.add(layers.Dropout(0.5))
    model.add(layers.Dense(64, activation='relu'))
    if dropout:
        model.add(layers.Dropout(0.5))
    model.add(layers.Dense(1, activation='sigmoid'))
    return model

def myprint(s, path=os.path.join("dst","2303_pez500","temp","modelSummary.txt")):
    with open(path,'a') as f:
        print(s, file=f)

def train(model=None, train_images=None, test_images=None, lr=None, cb_lst=[], trial=None):

    cb_earlystop= tf.keras.callbacks.EarlyStopping(
                monitor='val_loss',
                patience= 5,
                restore_best_weights=True,
                start_from_epoch=5
                )
    cb_lst.append(cb_earlystop)

    optimizerdict={
            "adam" : tf.keras.optimizers.Adam(learning_rate=lr),
            }
    model.compile(optimizer=optimizerdict['adam'],
                loss=tf.keras.losses.BinaryCrossentropy(),
                metrics=['accuracy'])
    history = model.fit(train_images, epochs=400, 
                        validation_data=(test_images), callbacks=cb_lst)
    return history

def analyse_model(model=None, val_dataset=None, dstpath=None, trialnr="", history=None):
    dstpath= os.path.join(dstpath,"temp")
    dsutils.clean_dir(dstpath)
    val_loss, val_acc = model.evaluate(val_dataset)
    y_pred_prob = model.predict(val_dataset)
    y_pred = [0 if y_pred_prob < 0.5 else 1]
    y_true = np.concatenate([y for x, y in val_dataset], axis=0)

    #plot loss and accuracy curve from training
    train_acc = history.history['accuracy']
    train_val_acc = history.history['val_accuracy']
    train_loss = history.history['loss']
    train_val_loss = history.history['val_loss']
    epochs = range(1, len(train_acc) + 1)
    xlim=int(len(epochs)/5+1)*5
    plt.plot(epochs, train_acc, label='Training acc')
    plt.plot(epochs, train_val_acc, label='Validation acc')
    plt.title('Training and validation accuracy', fontsize=18)
    ax = plt.gca()
    ax.set_ylim([0, 1])
    ax.set_xlim([0,xlim])
    plt.xlabel('Epoch', fontsize=18)
    plt.ylabel('Accuracy', fontsize=18)
    plt.legend()
    plt.savefig(os.path.join(dstpath,"trainacc"))
    plt.close("all")         

    plt.plot(epochs, train_loss, label='Training loss')
    plt.plot(epochs, train_val_loss, label='Validation loss')
    ax = plt.gca()
    ax.set_ylim([0, 2])
    ax.set_xlim([0,xlim])
    plt.xlabel('Epoch', fontsize=18)
    plt.ylabel('Loss', fontsize=18)
    plt.title('Training and validation loss', fontsize=18)
    plt.legend()
    plt.savefig(os.path.join(dstpath,"trainloss"))
    plt.close("all")      


    #confusion matrix
    class_names=("nodefect","defect")
    conf_matrix = confusion_matrix(y_true, y_pred)
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.matshow(conf_matrix, cmap=plt.cm.Blues, alpha=0.3)
    for i in range(len(conf_matrix)):
        for j in range(len(conf_matrix[1])):
            ax.text(x=j, y=i,s=conf_matrix[i][j], va='center', ha='center', size='xx-large')
    plt.xlabel('Predictions', fontsize=18)
    ax.xaxis.tick_bottom()
    ax.set_xticks([0,1])
    ax.set_xticklabels(class_names)
    plt.ylabel('Actuals', fontsize=18)
    ax.set_yticks([0,1])
    ax.set_yticklabels(class_names)
    plt.title(f'Confusion Matrix', fontsize=18)
    fig.savefig(dstpath+"/confusion"+str(trialnr))
    plt.close("all")      

    # calculating precision, recall and f1 score
    tn, fp, fn, tp = conf_matrix.ravel()
    precision=tp/(tp+fp) if fp !=0 and tp != 0 else 1
    recall=tp/(tp+fn)
    f1=tp/(tp+(fn+fp)/2)

    #ploting precision recall curve
    precisions, recalls, thresholds = precision_recall_curve(y_true,y_pred_prob)
    plt.plot(recalls, precisions) 
    plt.xlabel('Recall', fontsize=18)
    plt.ylabel('Precision', fontsize=18)
    plt.title(f'Precision-Recall (PR) Curve', fontsize=18)
    plt.savefig(dstpath+"/prereccurve"+trialnr)
    plt.close("all")

    #ploting precision recall curve
    precisions, recalls, thresholds = precision_recall_curve(y_true,y_pred_prob)
    plt.plot(recalls, precisions) 
    plt.xlabel('Recall', fontsize=18)
    plt.ylabel('Precision', fontsize=18)
    plt.title(f'Precision-Recall (PR) Curve', fontsize=18)
    plt.savefig(dstpath+"/prereccurve"+trialnr)
    plt.close("all")

    # plotting roc curve
    fpr, tpr, thresholds = roc_curve(y_true,y_pred_prob)
    plt.plot(fpr, tpr) 
    plt.xlabel('False Positiv Rate', fontsize=18)
    plt.ylabel('True Positive Rate', fontsize=18)
    plt.title(f'Receiver Operating Characteristic (ROC) Curve', fontsize=18)
    plt.savefig(dstpath+"/roccurve"+trialnr)
    plt.close("all")  

    # plotting det curve
    fpr, fnr, thresholds = det_curve(y_true, y_pred_prob)
    plt.plot(fpr, fnr) 
    plt.xlabel('False Positiv Rate', fontsize=18)
    plt.ylabel('False Negative Rate', fontsize=18)
    plt.title(f'Detection Error Tradeoff (DET) Curve', fontsize=18)
    plt.ylim([0,1])
    plt.xlim([0,1])
    plt.savefig(dstpath+"/detcurve"+trialnr)
    plt.close("all")

    finalmetrics = {
            "final_loss": val_loss,
            "final_acc": val_acc,
            "tp": tp,
            "fp": fp,
            "tn": tn,
            "fn": fn,
            "f1": f1,
            "precision": precision,
            "recall": recall,
            "roc_auc": roc_auc_score(y_true=y_true, y_score=y_pred_prob)
        }
    model.summary(print_fn=myprint) #write model to textfile for documentation
    print("Final val_acc: " + str(val_acc))
    return finalmetrics

def analyse_eval_model(model=None, val_dataset=None, dstpath=None):
    dstpath= os.path.join(dstpath,"temp")
    dsutils.clean_dir(dstpath)
    val_loss, val_acc = model.evaluate(val_dataset, batch_size = 1)
    y_pred_prob = model.predict(val_dataset)
    y_pred = [0 if x < 0.5 else 1 for x in y_pred_prob] #y_pred_prob.round().astype("int")
    y_true = np.concatenate([y for x, y in val_dataset], axis=0)
    #confusion matrix
    class_names=("nodefect","defect")
    conf_matrix = confusion_matrix(y_true, y_pred)
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.matshow(conf_matrix, cmap=plt.cm.Blues, alpha=0.3)
    for i in range(len(conf_matrix)):
        for j in range(len(conf_matrix[1])):
            ax.text(x=j, y=i,s=conf_matrix[i][j], va='center', ha='center', size='xx-large')
    plt.xlabel('Predictions', fontsize=18)
    ax.xaxis.tick_bottom()
    ax.set_xticks([0,1])
    ax.set_xticklabels(class_names)
    plt.ylabel('Actuals', fontsize=18)
    ax.set_yticks([0,1])
    ax.set_yticklabels(class_names)
    plt.title(f'Confusion Matrix', fontsize=18)
    fig.savefig(dstpath+"/eval_confusion")
    plt.close("all")      

    # calculating precision, recall and f1 score
    tn, fp, fn, tp = conf_matrix.ravel()
    precision=tp/(tp+fp) if fp !=0 and tp != 0 else 1
    recall=tp/(tp+fn)
    f1=tp/(tp+(fn+fp)/2)

    #ploting precision recall curve
    precisions, recalls, thresholds = precision_recall_curve(y_true,y_pred_prob)
    plt.plot(recalls, precisions) 
    plt.xlabel('Recall', fontsize=18)
    plt.ylabel('Precision', fontsize=18)
    plt.title(f'Precision-Recall (PR) Curve', fontsize=18)
    plt.savefig(dstpath+"/eval_prereccurve")
    plt.close("all")

    #ploting precision recall curve
    precisions, recalls, thresholds = precision_recall_curve(y_true,y_pred_prob)
    plt.plot(recalls, precisions) 
    plt.xlabel('Recall', fontsize=18)
    plt.ylabel('Precision', fontsize=18)
    plt.title(f'Precision-Recall (PR) Curve', fontsize=18)
    plt.savefig(dstpath+"/eval_prereccurve")
    plt.close("all")

    # plotting roc curve
    fpr, tpr, thresholds = roc_curve(y_true,y_pred_prob)
    plt.plot(fpr, tpr) 
    plt.xlabel('False Positiv Rate', fontsize=18)
    plt.ylabel('True Positive Rate', fontsize=18)
    plt.title(f'Receiver Operating Characteristic (ROC) Curve', fontsize=18)
    plt.savefig(dstpath+"/eval_roccurve")
    plt.close("all")  

    # plotting det curve
    fpr, fnr, thresholds = det_curve(y_true, y_pred_prob)
    plt.plot(fpr, fnr) 
    plt.xlabel('False Positiv Rate', fontsize=18)
    plt.ylabel('False Negative Rate', fontsize=18)
    plt.title(f'Detection Error Tradeoff (DET) Curve', fontsize=18)
    plt.ylim([0,1])
    plt.xlim([0,1])
    plt.savefig(dstpath+"/eval_detcurve")
    plt.close("all")

    finalmetrics = {
            "final_loss": val_loss,
            "final_acc": val_acc,
            "tp": tp,
            "fp": fp,
            "tn": tn,
            "fn": fn,
            "f1": f1,
            "precision": precision,
            "recall": recall,
            "roc_auc": roc_auc_score(y_true=y_true, y_score=y_pred_prob)
        }
    strfinalmetrics = {}
    for key in finalmetrics.keys():
        strfinalmetrics[key] = str(finalmetrics[key])
    with open(os.path.join(dstpath,"eval_metrics.yaml"),"w") as f:
        f.write(json.dumps(strfinalmetrics, indent=4))
    return finalmetrics

def main(cb_lst=[], model=None):
    config = dsutils.load_setup(os.path.join("configs","pipeline05config.yaml"))
    srcpath = config["Paths"]["srcpath"]

    batchsize = config["Hyperparameters"]["batch_size"]
    cnnlyrs = config["Hyperparameters"]["cnnlyrs"]
    initialfilternr = config["Hyperparameters"]["initialfilternr"]
    dropout= config["Hyperparameters"]["dropout"]
    normalization = config["Hyperparameters"]["normalization"]
    lr=config["Hyperparameters"]["lr_adam"]

    #get one image to extract image dimensions
    for dirpath, _, filenames in os.walk(srcpath):
        for filename in filenames:
            if filename.endswith(".png"):
                with tf.keras.preprocessing.image.load_img(os.path.join(dirpath, filename)) as img:
                    image_size = (img.height, img.width)
            break
    ds_train, ds_val = load_ds(os.path.join(srcpath,"data"), batch_size=batchsize, image_size=image_size)
    if model == None: model = create_model(input_size=image_size, cnnlyrs=cnnlyrs, initialfilternr=initialfilternr, dropout=dropout, normalization=normalization)
    history = train(model, ds_train, ds_val, lr=lr)
    final_metrics=analyse_model(model=model, val_dataset=ds_val, dstpath=srcpath, history=history)
    return final_metrics["final_acc"]

def eval(modelpath):
    srcpath = 'dst/2303_pez500EVALUATION'
    image_size = (98,325)

    ds_eval = load_evalds(os.path.join(srcpath,"data"), batch_size=1, image_size=image_size)
    model = tf.keras.models.load_model(modelpath)
    #preds = model.predict(ds_eval)
    #print(preds == model.predict(ds_eval))
    final_metrics=analyse_eval_model(model=model, val_dataset=ds_eval, dstpath=srcpath)

    # extrakt misclassified images
    datadirs=[os.path.join(srcpath,'data','defect'),os.path.join(srcpath,'data','nodefect')]
    lst_fn=[]
    lst_fp=[]
    lst_unclear = []
    dict_class={'defect':1, 'nodefect':0}
    for directory in datadirs:
        print(directory)
        target = dict_class[os.path.split(directory)[1]]
        imagelst = glob.glob(os.path.join(directory,'*.png'))
        for imgpath in imagelst:
            img = cv2.imread(imgpath)
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            img= np.expand_dims(img, axis=0)
            img= img/255
            pred_prob=model.predict(img, verbose=0)
            pred = 0 if pred_prob < 0.5 else 1
            img=np.squeeze(img)
            if pred_prob not in [0,1]:
                lst_unclear.append((img,imgpath))
            if pred != target:
                if target == 1:
                    lst_fn.append((img,'defect', imgpath))
                else:
                    lst_fp.append((img,'nodefect',imgpath))
    misclasspath=os.path.join(srcpath,'temp','eval_misclassified')
    dsutils.clean_dir(misclasspath)
    for img, label, path in lst_fp:
        name = os.path.split(path)[1].split('.')[0]
        plt.imsave(os.path.join(misclasspath,f'fp_{name}.png'),img, cmap='gray')
    for img, label, path in lst_fn:
        name = os.path.split(path)[1].split('.')[0]
        plt.imsave(os.path.join(misclasspath,f'fn_{name}.png'),img, cmap='gray')



    return final_metrics


if __name__ == "__main__":
    #main()
    print(eval('models/pipe5_run11_trial372_Acc983_1.hdf5'))