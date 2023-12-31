import dsutils
import os
import glob
import pandas as pd
import matplotlib.pyplot as plt

def main(dstpath, labels_df,cut_vals):
    convert_csv2png(dstpath=dstpath,labels_df=labels_df, cut_vals=cut_vals)

def convert_csv2png(dstpath, labels_df, cut_vals):
    convdstpath = f"{dstpath}" #destination to save converted images
    dsutils.clean_dir(convdstpath) #if not exists creates destination path or else deletes everything in it
    for index, row in labels_df.iterrows():
        imgpath = row["paths"]
        label = row["labels"]
        img=pd.read_csv(imgpath).to_numpy()
        cropped_img = crop_img(img=img, cut_vals=cut_vals)

        #generate new saving path
        fdir,orig_fname = os.path.split(imgpath)
        new_fname = orig_fname.split(".")[0]
        savepath=os.path.join(convdstpath,label,new_fname+".png")
     
        if not os.path.exists("/".join(savepath.split("/")[:-1])):
             dsutils.clean_dir("/".join(savepath.split("/")[:-1]))
        _=plt.imsave(savepath,cropped_img, cmap='gray')

def crop_img(img, cut_vals):
    hight,width = img.shape
    croppedimg = img[cut_vals["top"]:hight-cut_vals["bottom"], cut_vals["left"]:width-cut_vals["right"]]
    return croppedimg

def gen_labelescsv(dstpath):
    files=glob.glob(os.path.join(dstpath,"*","cdata*.png"), recursive=True)
    files.sort()
    files_df=pd.DataFrame(files, index=[x+1 for x in range(len(files))])
    files_df.columns=["paths"]
    files_df["labels"]=files_df.paths.apply(lambda x: os.path.split(os.path.split(x)[0])[1])
    files_df.to_csv(os.path.join(dstpath,"labels.csv"))

if __name__ == "__main__":
    srcpath = os.path.join("src","2303_pez500","evaluationset")
    labels_df_path = "src/2303_pez500/2303_pez500_eval_labels.csv"
    dstpath = os.path.join("dst","2303_pez500EVALUATION",'data')
    cut_vals={"bottom":70,
            "left":0,
            "top":0,
            "right":2}
    labels_df = pd.read_csv(labels_df_path, index_col=0)
    main(dstpath=dstpath, labels_df=labels_df, cut_vals=cut_vals)
    gen_labelescsv(dstpath)