import optuna
import yaml
import pipeline03_IMG_CNNOptPooling as pipe
import mlflow
import tensorflow as tf
import datetime
import os
import Scripts.dsutils as dsutils

configpath = "configs/pipeline05config.yaml"
experiment_name= "pipeline05_IMG_CNN_11_OptPooling2"

best_loss = None
best_acc = None

def objective(trial):
    # function to be optimized by optuna
    
    tf.keras.backend.clear_session() #clear old tensorflow data

    #global variables to save best values and save best models
    global experiment_name
    global best_loss
    global best_acc

    # start mlflow logging
    mlflow.set_tracking_uri(f"sqlite:///MLFlow.db") #configures local sqlite database as logging target
    mlflow.set_experiment(experiment_name=experiment_name) # creating experiment under which future runs will get logged
    experiment_id=mlflow.get_experiment_by_name(experiment_name).experiment_id # extracting experiment ID to be able to manually start runs in that scope
    
    #add callbacks fro tracking and pruning
    cb_lst = []
    cb_mlflow =  tf.keras.callbacks.LambdaCallback(on_epoch_end=lambda epoch, logs: mlflow.log_metrics(metrics=logs, step=epoch))
    cb_lst.append(cb_mlflow)
    cb_lst.append(optuna.integration.TFKerasPruningCallback(trial, "val_accuracy"))

    with mlflow.start_run(experiment_id=experiment_id, run_name=f"Trial {trial.number}"):
        mlflow.set_tag("pruned",True)

        #load config and set parameters
        with open(configpath) as f:
            config=yaml.safe_load(f)
        initialfilternr=config["Hyperparameters"]["nr_filter"]=trial.suggest_categorical('nr_filter', [8,16,32,64,128,256])
        cnnlyrs=config["Hyperparameters"]["nr_layers"]=trial.suggest_int('nr_layers', 0, 5)
        batchsize=config["Hyperparameters"]["batch_size"]=trial.suggest_categorical('batch_size', [280,140,70,56,40,35,28,20,14,10,8,7,5,4,2,1])
        lr=config["Hyperparameters"]["lr_adam"]=trial.suggest_float('lr_adam', 0.0001, 0.1)
        dropout=config["Hyperparameters"]["dropout"]=trial.suggest_categorical('dropout', [True, False])
        normalization=config["Hyperparameters"]["normalization"]=trial.suggest_categorical('normalization', [True, False])
        pooling=config["Hyperparameters"]["pooling"]=trial.suggest_categorical('pooling', [True, False])
        srcpath = config["Paths"]["srcpath"]
        imgwidth = config["General"]["imagewidth"]
        imghight = config["General"]["imagehight"]
        #get one image to extract image dimensions
        image_size = (imghight, imgwidth)      

        #log parameters
        mlflow.log_params(config["Hyperparameters"])

        #write new parameters to file
        with open(configpath, 'w') as outfile:
            yaml.dump(config, outfile, default_flow_style=False)

        #Clear clutter from previous TensorFlow graphs and matplotlib plots.
        dsutils.clean_dir(os.path.join(srcpath,"temp"))        
        #create model (try except block due catching errors for impossible models)
        try:
            model=pipe.create_model(input_size=image_size, cnnlyrs=cnnlyrs, initialfilternr=initialfilternr, dropout=dropout, normalization=normalization, pooling=pooling)
            #load dataset
            ds_train, ds_val = pipe.load_ds(os.path.join(srcpath,"data"), batch_size=batchsize, image_size=image_size)
            history = pipe.train(model, ds_train, ds_val, lr=lr, trial=trial, cb_lst=cb_lst)
            final_metrics=pipe.analyse_model(model=model, val_dataset=ds_val, dstpath=srcpath, history=history)
            if best_loss == None or best_loss >= final_metrics["final_loss"] or best_acc<= final_metrics["final_acc"]:
                best_loss = final_metrics["final_loss"]
                best_acc = final_metrics["final_acc"]
                model.save(os.path.join(srcpath,"temp","model.hdf5"))
                mlflow.set_tag("model",True)
            mlflow.log_metrics(final_metrics)
            mlflow.log_artifacts(os.path.join(srcpath,"temp"))
            mlflow.set_tag("pruned",False)
            return  final_metrics["final_acc"]
        except ValueError as e: 
            if trial.should_prune() == False:
                print("*************************************")
                print("ValueError")
                print("*************************************")
                with open(os.path.join(srcpath,"temp","exception.txt"), "w") as f:
                    f.write(str(e))
                mlflow.set_tag("valerror",True)
                mlflow.log_artifacts(os.path.join(srcpath,"temp"))          
            raise optuna.TrialPruned()
        except optuna.exceptions.TrialPruned as e:
            raise optuna.TrialPruned()
        except Exception as e:
            print("*************************************")
            print("Crashed")
            print("*************************************")
            with open(os.path.join(srcpath,"temp","exception.txt"), "w") as f:
                f.write(str(e))
            mlflow.set_tag("crashed",True)
            mlflow.log_artifacts(os.path.join(srcpath,"temp"))
            raise optuna.TrialPruned()

study = optuna.create_study(study_name=experiment_name, direction='maximize', storage="sqlite:///optuna.db", load_if_exists=True)

study.optimize(objective, n_trials=500)

bestparams = study.best_params
with open(configpath) as f:
        config=yaml.safe_load(f)
        config["Hyperparameters"]=config["Hyperparameters"]|bestparams
with open(f"{configpath[:-5]}best.yaml", 'w') as outfile:
    yaml.dump(config, outfile, default_flow_style=False)