import optuna
import yaml
import pipeline_RF_MLP

configpath = "configs/pipeline04config.yaml"
best_acc = 0.0

def objective(trial):
    with open(configpath) as f:
        config=yaml.safe_load(f)
    #config["Hyperparameters"]["loss"]=trial.suggest_categorical('loss', ["binary_crossentropy"])
    config["Hyperparameters"]["neurons"]=trial.suggest_int('neurons', 64, 128*57*3/2)
    config["Hyperparameters"]["layers"]=trial.suggest_int('layers', 0, 3)
    config["Hyperparameters"]["batch_size"]=trial.suggest_int('batch_size', 2, 128)
    config["Hyperparameters"]["lr_adam"]=trial.suggest_float('lr_adam', 0.00000001, 0.1)
    with open(configpath, 'w') as outfile:
        yaml.dump(config, outfile, default_flow_style=False)
    pipeline = pipeline_RF_MLP.pipe_deladetect(trial=trial)
    pipeline.run_pipeline()
    if best_acc < pipeline.acc:
        pipeline.model.save(f'{pipeline.srcpath}/mosdel/model.hdf5')
    return  pipeline.acc

study = optuna.create_study(study_name="Pipeline4_RF_MLP", direction='maximize', storage="sqlite:///optuna.sqlite3", load_if_exists=True)

study.optimize(objective, n_trials=500)

bestparams = study.best_params

with open(configpath) as f:
        config=yaml.safe_load(f)
        config["Hyperparameters"]["neurons"] = bestparams["neurons"]
        config["Hyperparameters"]["layers"] = bestparams["layers"]        
        config["Hyperparameters"]["batch_size"] = bestparams["batch_size"]        
        config["Hyperparameters"]["lr_adam"] = bestparams["lr_adam"]
with open(f"{configpath[:-5]}best.yaml", 'w') as outfile:
    yaml.dump(config, outfile, default_flow_style=False)

