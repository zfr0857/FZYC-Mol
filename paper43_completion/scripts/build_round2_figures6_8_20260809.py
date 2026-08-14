from __future__ import annotations
from pathlib import Path
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT=Path(r"D:\fzyc")
PKG=ROOT/"output"/"Journal_of_Cheminformatics_submission_round2_20260809"
OUT=PKG/"03_Figures"
SRC=PKG/"04_Source_data"/"machine_readable_source_tables"/"main_figures"
OLD=ROOT/"output"/"paper43_jcheminform_completion_20260726"/"source_data"
BLUE="#3B6EA8"; ORANGE="#D4813A"; TEAL="#2A8C82"; PURPLE="#8064A2"; GREY="#7A7F87"; LIGHT="#E6E9EC"; INK="#202830"
DISPLAY={"bace":"BACE","bbbp":"BBBP","clintox":"ClinTox","tdc_hia_hou":"HIA","tdc_pgp_broccatelli":"P-gp"}
mpl.rcParams.update({"font.family":"Times New Roman","font.size":9,"axes.titlesize":10.2,"axes.titleweight":"bold","axes.labelsize":9.2,
                     "xtick.labelsize":8.2,"ytick.labelsize":8.2,"legend.fontsize":8.1,"axes.spines.top":False,"axes.spines.right":False,
                     "pdf.fonttype":42,"svg.fonttype":"none","axes.unicode_minus":False})

def save(fig,n):
    fig.savefig(OUT/f"Figure{n}.pdf",bbox_inches="tight",facecolor="white")
    fig.savefig(OUT/f"Figure{n}.svg",bbox_inches="tight",facecolor="white")
    fig.savefig(OUT/f"Figure{n}_600dpi.png",dpi=600,bbox_inches="tight",facecolor="white")
    plt.close(fig)

def label(ax,l,t):
    ax.text(-.17,1.06,l,transform=ax.transAxes,fontsize=13,fontweight="bold",color=BLUE,va="bottom")
    ax.text(-.06,1.06,t,transform=ax.transAxes,fontsize=10.2,fontweight="bold",va="bottom")

def figure6():
    mat=pd.read_csv(SRC/"Figure_6A_double_triangle_matrix_source.csv")
    b=pd.read_csv(SRC/"Figure_6B_support_risk_matrix_source.csv")
    c=pd.read_csv(SRC/"Figure_6C_scaffold_reliability_source.csv")
    d=pd.read_csv(SRC/"Figure_6D_four_model_clintox_source.csv")
    fig,axs=plt.subplots(2,2,figsize=(7.2,5.92),gridspec_kw={"hspace":.48,"wspace":.62})
    models=list(dict.fromkeys(mat.row_model.tolist()+mat.column_model.tolist()))
    pred=np.full((len(models),len(models)),np.nan); err=pred.copy(); err=np.full_like(pred,np.nan)
    pos={m:i for i,m in enumerate(models)}
    for r in mat.itertuples():
        i,j=pos[r.row_model],pos[r.column_model]
        (pred if r.metric=="prediction_correlation" else err)[i,j]=r.value
    ax=axs[0,0]
    ax.imshow(np.ma.masked_invalid(pred),cmap="Blues",vmin=0,vmax=1)
    ax.imshow(np.ma.masked_invalid(err),cmap="Purples",vmin=0,vmax=1)
    for i in range(len(models)):
        for j in range(len(models)):
            val=pred[i,j] if np.isfinite(pred[i,j]) else err[i,j]
            if np.isfinite(val): ax.text(j,i,f"{val:.2f}",ha="center",va="center",fontsize=8,color="white" if val>.55 else INK)
    names=["RF","GCN","ChemBERTa","MolFormer"]
    ax.set(xticks=np.arange(4),xticklabels=names,yticks=np.arange(4),yticklabels=names)
    ax.tick_params(length=0); label(ax,"A","Prediction and error similarity")

    ax=axs[0,1]
    labels=list(dict.fromkeys(b.display_label)); bins=list(dict.fromkeys(b.tanimoto_bin))
    vals=np.array([[b[(b.display_label==lab)&(b.tanimoto_bin==bn)]["median"].iloc[0] for bn in bins] for lab in labels],float)
    adverse=np.zeros_like(vals)
    for i,lab in enumerate(labels):
        row=b[b.display_label.eq(lab)]; direction=row.direction.iloc[0]
        span=max(vals[i].max()-vals[i].min(),1e-12)
        adverse[i]=(vals[i].max()-vals[i])/span if direction=="higher_is_better" else (vals[i]-vals[i].min())/span
    ax.imshow(adverse,cmap="cividis_r",vmin=0,vmax=1,aspect="auto")
    for i in range(vals.shape[0]):
        for j in range(vals.shape[1]): ax.text(j,i,f"{vals[i,j]:.3f}",ha="center",va="center",fontsize=8,color="white" if adverse[i,j]>.55 else INK)
    ax.set(xticks=np.arange(len(bins)),xticklabels=["Low","Intermediate","High"],yticks=np.arange(len(labels)),yticklabels=labels,xlabel="Chemical support")
    ax.tick_params(length=0); label(ax,"B","Chemical-support performance and risk")

    ax=axs[1,0]; yy=np.arange(len(c))
    for i,r in enumerate(c.itertuples()):
        ax.hlines(i,r.q025,r.q975,color=GREY,lw=1.1); ax.scatter(r.median_ratio,i,color=[PURPLE,ORANGE,TEAL,BLUE][i%4],s=36,zorder=3)
    ax.axvline(1,color=INK,lw=.8); ax.set_xscale("log",base=2); ax.set(yticks=yy,yticklabels=c.label,xlabel="Novel / seen-or-related scaffold ratio")
    ax.invert_yaxis(); ax.grid(axis="x",color=LIGHT,lw=.6); label(ax,"C","Novel-scaffold reliability shifts")

    ax=axs[1,1]
    metrics=[("mean_roc_auc","ROC-AUC",BLUE,"o"),("mean_pr_auc","PR-AUC",TEAL,"D"),("minority_recall","Recall",ORANGE,"o"),("minority_false_negative_rate","FNR","#B65757","s"),("mean_class_1_coverage","Coverage",PURPLE,"^")]
    names={"rdkit_rf":"RF","gnn_gcn":"GCN","chemberta_mtr_linear_probe":"ChemBERTa","molformer_linear_probe":"MolFormer"}
    y=np.arange(len(d))
    for off,(col,name,color,mark) in zip(np.linspace(-.22,.22,len(metrics)),metrics):
        ax.scatter(d[col],y+off,color=color,marker=mark,s=30,label=name)
    ax.axvline(.90,color=PURPLE,lw=.8,ls="--"); ax.set(yticks=y,yticklabels=[names.get(x,x) for x in d.candidate],xlim=(0,1),xlabel="Natural metric scale")
    ax.invert_yaxis(); ax.grid(axis="x",color=LIGHT,lw=.6); ax.legend(frameon=False,ncol=3,loc="lower center",bbox_to_anchor=(.5,-.43)); label(ax,"D","ClinTox four-model trade-offs")
    fig.subplots_adjust(left=.15,right=.98,top=.94,bottom=.13)
    save(fig,6)

def figure8():
    fixed=pd.read_csv(OLD/"fixed_reference_units.csv")
    eps=pd.read_csv(OLD/"epsilon_near_equivalence_units.csv")
    comp=pd.read_csv(SRC/"classification_metric_selector_comparisons_final.csv")
    ks=[4,8,16,32]
    working=eps[((eps.task_type=="classification")&(eps.epsilon==.010))|((eps.task_type=="regression")&(eps.epsilon==.050))]
    fig=plt.figure(figsize=(7.2,6.0)); gs=fig.add_gridspec(2,3,left=.09,right=.98,bottom=.10,top=.92,hspace=.48,wspace=.46,width_ratios=[1.25,1,1])
    sub=gs[:,0].subgridspec(2,1,hspace=.42); axes=[]
    estim=[("fixed_k32_gap","-","K-invariant"),("k_dependent_crossfit_gap","--","K-dependent"),("same_fold_opportunity_gap",":","Same-fold")]
    for i,(task,color,mark,ylab) in enumerate([("classification",BLUE,"o","ROC-AUC gap"),("regression",ORANGE,"s","RMSE gap")]):
        ax=fig.add_subplot(sub[i]); q=fixed[fixed.task_type.eq(task)]
        for col,ls,nm in estim:
            z=q.groupby("pool_size")[col].mean().reindex(ks); ax.plot(z.index,z,color=color,marker=mark,ls=ls,lw=1.2,ms=4,label=nm)
        ax.axhline(0,color=GREY,lw=.8); ax.set(xticks=ks,ylabel=ylab); ax.grid(axis="y",color=LIGHT,lw=.6)
        if i==1: ax.set_xlabel("Candidate count, K")
        else: ax.tick_params(labelbottom=False)
        axes.append(ax)
    label(axes[0],"A","Reference and opportunity gaps")
    axes[0].legend(frameon=False,ncol=1,loc="upper right",fontsize=7.8)

    for spec,metric,ylab,letter,title in [(gs[0,1],"crossfit_epsilon_success","Success (%)","B","Practical-equivalence success"),(gs[1,1],"crossfit_near_equivalent_n","Mean set size","C","Near-equivalent candidate sets")]:
        ax=fig.add_subplot(spec)
        for task,name,color,mark in [("classification","Classification",BLUE,"o"),("regression","Regression",ORANGE,"s")]:
            z=working[working.task_type.eq(task)].groupby("pool_size")[metric].mean().reindex(ks); z=100*z if "success" in metric else z
            ax.plot(z.index,z,color=color,marker=mark,lw=1.2,label=name)
        ax.set(xticks=ks,xlabel="Candidate count, K",ylabel=ylab); ax.grid(axis="y",color=LIGHT,lw=.6); label(ax,letter,title)
        if letter=="B": ax.legend(frameon=False)

    endpoints=["bace","bbbp","clintox","tdc_hia_hou","tdc_pgp_broccatelli"]
    k32=comp[comp.pool_size.eq(32)&comp.alternative_selector.eq("pr_auc")].groupby("dataset").mean(numeric_only=True).reindex(endpoints)
    ax=fig.add_subplot(gs[0,2]); sw=100*k32.candidate_changed_vs_roc.to_numpy()
    ax.barh(np.arange(5),sw,color=TEAL,edgecolor="white"); ax.set(yticks=np.arange(5),yticklabels=[DISPLAY[x] for x in endpoints],xlim=(0,100),xlabel="Candidate switching (%)")
    ax.invert_yaxis(); ax.grid(axis="x",color=LIGHT,lw=.6); label(ax,"D","PR-AUC candidate switching")
    for i,v in enumerate(sw): ax.text(v+2,i,f"{v:.0f}%",va="center",fontsize=8)
    ax=fig.add_subplot(gs[1,2]); ef=k32.delta_outer_pr_auc_vs_roc_selector.to_numpy()
    colors=np.where(ef>=0,BLUE,ORANGE); ax.scatter(ef,np.arange(5),c=colors,s=42)
    ax.axvline(0,color=INK,lw=.8); ax.set(yticks=np.arange(5),yticklabels=[DISPLAY[x] for x in endpoints],xlabel=r"Outer $\Delta$PR-AUC")
    ax.invert_yaxis(); ax.grid(axis="x",color=LIGHT,lw=.6); label(ax,"E","Outer PR-AUC change")
    fig.subplots_adjust(left=.12,right=.98,top=.92,bottom=.10)
    save(fig,8)

if __name__=="__main__":
    figure6(); figure8(); print(OUT)
