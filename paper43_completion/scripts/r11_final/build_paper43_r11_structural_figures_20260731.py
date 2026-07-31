from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.ticker import NullFormatter
from PIL import Image


ROOT = Path(r"D:\fzyc")
PACKAGE = ROOT / "output" / "paper43_jcheminform_completion_20260726"
OUT = ROOT / "work" / "r11_structural_figures_20260731"
TABLES = PACKAGE / "additional_files" / "tables"
MINOR = ROOT / "output" / "paper25_pre_submission_minor_revision_20260715"
ANALYSIS = ROOT / "output" / "paper22_major_revision_20260713"
BLUE, ORANGE, TEAL, PURPLE = "#315E8A", "#D58135", "#2F8B83", "#78689A"
GREY, RED, INK, LIGHT = "#7A7F87", "#B85C5C", "#202830", "#E3E7EA"
DISPLAY = {"bace":"BACE","bbbp":"BBBP","clintox":"ClinTox","esol":"ESOL","freesolv":"FreeSolv",
           "lipo":"Lipophilicity","tdc_caco2_wang":"Caco2","tdc_hia_hou":"HIA","tdc_pgp_broccatelli":"P-gp"}


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); assert spec.loader
    spec.loader.exec_module(module); return module


def setup():
    mpl.rcParams.update({"font.family":"Times New Roman","font.serif":["Times New Roman"],"font.size":9,
        "axes.titlesize":10.3,"axes.titleweight":"bold","axes.labelsize":9.2,"xtick.labelsize":8.2,
        "ytick.labelsize":8.2,"legend.fontsize":8.2,"axes.linewidth":.75,"axes.spines.top":False,
        "axes.spines.right":False,"pdf.fonttype":42,"ps.fonttype":42,"svg.fonttype":"none",
        "mathtext.fontset":"custom","mathtext.rm":"Times New Roman","mathtext.it":"Times New Roman:italic",
        "axes.unicode_minus":False,"savefig.facecolor":"white","figure.facecolor":"white"})


def save(fig, number):
    OUT.mkdir(parents=True, exist_ok=True)
    for item in fig.findobj(match=mpl.text.Text):
        if item.get_text() and item.get_fontsize() < 8: item.set_fontsize(8)
    for ext, kw in [("svg",{}),("pdf",{}),("png",{"dpi":600})]:
        path = OUT / (f"Figure{number}_600dpi.png" if ext == "png" else f"Figure{number}.{ext}")
        fig.savefig(path, bbox_inches="tight", facecolor="white", **kw)
        if ext == "png":
            with Image.open(path) as im: im.convert("RGB").save(path, dpi=(600,600), compress_level=6)
    plt.close(fig)


def clean(ax, axis="y"):
    ax.grid(axis=axis, color=LIGHT, lw=.6, alpha=.8); ax.set_axisbelow(True)


def header(fig, spec, letter, title):
    sub=spec.subgridspec(2,1,height_ratios=[.15,.85],hspace=0)
    h=fig.add_subplot(sub[0]); h.axis("off")
    h.text(-.10,.20,letter,fontsize=12,fontweight="bold",va="bottom")
    h.text(.02,.20,title,fontsize=10.3,fontweight="bold",va="bottom")
    return sub[1]


def figure1():
    os.environ["FZYC_FIG_OUT"] = str(OUT)
    os.environ["FZYC_FINAL_OUT"] = str(OUT)
    os.environ["FZYC_ANALYSIS_OUT"] = str(ANALYSIS)
    p21=load_module(ROOT/"scripts"/"build_paper21_final_figures.py","p21_r11")
    p21.setup(); p21.figure1()


def figure3():
    ranking=pd.read_csv(MINOR/"ranking_metric_main_summary.csv").sort_values("candidate_count")
    null=pd.read_csv(MINOR/"mechanism_permutation_null_summary.csv")
    signal=pd.read_csv(MINOR/"mechanism_signal_recovery_summary.csv")
    controls=pd.read_csv(ANALYSIS/"candidate_composition_controls.csv")
    effects=pd.read_csv(TABLES/"fixed_reference_k32_vs_k4_contrasts.csv")
    effects=effects[effects.estimand.eq("fixed_k32_gap")]
    effects.to_csv(OUT/"Figure_3A_primary_ten_seed_source.csv",index=False,encoding="utf-8-sig")
    fig=plt.figure(figsize=(6.69,5.55)); gs=fig.add_gridspec(2,2,left=.105,right=.98,bottom=.08,top=.985,hspace=.42,wspace=.48)
    contents=[]
    titles=["K-invariant completion-gap contrasts","Chance-adjusted top-rank recovery","Signal-recovery calibration","Candidate-composition controls"]
    for spec,letter,title in zip(gs,"ABCD",titles): contents.append((header(fig,spec,letter,title),spec))
    a=contents[0][0].subgridspec(1,2,wspace=.82)
    for ax,kind,color,xlabel,order in [
        (fig.add_subplot(a[0]),"classification",BLUE,"ROC-AUC contrast",["bbbp","tdc_pgp_broccatelli","bace","clintox","tdc_hia_hou"]),
        (fig.add_subplot(a[1]),"regression",ORANGE,"RMSE contrast",["lipo","freesolv","tdc_caco2_wang","esol"])]:
        q=effects[effects.task_type.eq(kind)].set_index("dataset").loc[order].reset_index(); y=np.arange(len(q))
        x=q.mean_natural_scale_effect.to_numpy(); lo=q.seed_block_interval_low.to_numpy(); hi=q.seed_block_interval_high.to_numpy()
        ax.errorbar(x,y,xerr=[x-lo,hi-x],fmt="none",ecolor=GREY,capsize=2.4,lw=1)
        for xi,yi,li,hii in zip(x,y,lo,hi):
            sig=li>0 or hii<0; ax.scatter(xi,yi,s=31,facecolors=color if sig else "white",edgecolors=color,zorder=3)
        ax.axvline(0,color=INK,lw=.8); ax.set(yticks=y,yticklabels=[DISPLAY[x] for x in q.dataset],xlabel=xlabel)
        ax.tick_params(axis="y",labelsize=8); clean(ax,"x")
    ax=fig.add_subplot(contents[1][0]); env=null.groupby("candidate_count",as_index=False).agg(lo=("null_q025","min"),hi=("null_q975","max"))
    ax.fill_between(env.candidate_count,env.lo,env.hi,color=GREY,alpha=.15,label="Permutation 95% envelope")
    ax.plot(ranking.candidate_count,ranking.chance_adjusted_hit_median,"o-",color=BLUE,label="CAHit@3")
    ax.plot(ranking.candidate_count,ranking.normalized_mrr_gain_median,"s-",color=TEAL,label="Normalized MRR gain")
    ax.axhline(0,color=GREY,lw=.8); ax.set(xlabel="Candidate count, K",ylabel="Chance-adjusted score",xticks=[4,8,16,32]); ax.legend(frameon=False,fontsize=8); clean(ax)
    ax=fig.add_subplot(contents[2][0])
    for k,c,m in zip([4,8,16,32],[BLUE,TEAL,ORANGE,PURPLE],["o","s","^","D"]):
        q=signal[signal.candidate_count.eq(k)].sort_values("injected_signal"); ax.plot(q.injected_signal,q.chance_adjusted_hit_median,marker=m,color=c,label=f"K = {k}")
    ax.axhline(0,color=GREY,lw=.8); ax.set(xlabel="Injected validation–audit signal",ylabel="Median CAHit@3"); ax.legend(frameon=False,ncol=2); clean(ax)
    ax=fig.add_subplot(contents[3][0])
    for mode,c,m in zip(sorted(controls["mode"].unique()),[BLUE,TEAL,ORANGE,PURPLE,GREY,RED],["o","s","^","D","P","X"]):
        q=controls[controls["mode"].eq(mode)].sort_values("pool_size"); ax.plot(q.pool_size,q.chance_adjusted_hit_mean,marker=m,color=c,label=mode.replace("_"," "),lw=1.2)
    ax.axhline(0,color=GREY,lw=.8); ax.set(xlabel="Candidate count, K",ylabel="Chance-adjusted hit",xticks=[4,8,16,32]); ax.legend(frameon=False,ncol=2,fontsize=8); clean(ax)
    save(fig,3)


def figure7():
    p31=load_module(ROOT/"scripts"/"build_paper31_figures_20260717.py","p31_r11"); p31.style(); setup(); data=p31.load()
    summary=data["summary"]; units=data["units"]; budget=data["budget_units"]
    pools,tasks,ks=p31.POOLS,p31.TASKS,p31.KS; colors=p31.COLORS; labels=p31.TASK_LABEL
    base=summary[summary.design.eq("equal_K")&summary.anchor_scheme.eq("shared_morgan_linear")]
    fig=plt.figure(figsize=(6.69,6.10)); gs=fig.add_gridspec(2,2,left=.14,right=.985,bottom=.075,top=.90,hspace=.48,wspace=.40)
    asub=gs[0,0].subgridspec(1,2,wspace=.12); k32=base[base.candidate_count.eq(32)]
    arrays=[k32.pivot_table(index="task",columns="pool",values=m).reindex(index=tasks,columns=pools).to_numpy(float) for m in ["homogeneous_normalized_selected_gain_mean","homogeneous_normalized_oracle_opportunity_mean"]]
    lim=max(float(np.nanquantile(np.abs(np.concatenate([a.ravel() for a in arrays])),.98)),1e-6)
    for idx,(arr,title) in enumerate(zip(arrays,["Selected gain","Audit-best opportunity"])):
        ax=fig.add_subplot(asub[idx]); mesh=ax.pcolormesh(np.arange(4),np.arange(7),arr,cmap="RdBu_r",vmin=-lim,vmax=lim,shading="flat")
        ax.set(xlim=(0,3),ylim=(6,0)); ax.set_xticks(np.arange(3)+.5,["H","MV","M"]); ax.set_yticks(np.arange(6)+.5,[labels[t] for t in tasks] if idx==0 else []); ax.set_title(title,fontsize=9.2,pad=2)
        for i in range(6):
            for j in range(3):
                rgba=mesh.cmap(mesh.norm(arr[i,j])); lum=.2126*rgba[0]+.7152*rgba[1]+.0722*rgba[2]
                ax.text(j+.5,i+.5,f"{arr[i,j]:.2f}",ha="center",va="center",fontsize=8,color="white" if lum<.5 else "black")
        for s in ax.spines.values(): s.set_visible(False)
    fig.text(gs[0,0].get_position(fig).x0,.975,"A  Endpoint-level opportunity at K = 32",fontsize=10.3,fontweight="bold",va="top")
    bsub=gs[0,1].subgridspec(1,2,wspace=.28)
    for idx,kind in enumerate(["classification","regression"]):
        ax=fig.add_subplot(bsub[idx])
        for pool in pools:
            part=base[(base.pool.eq(pool))&base.task_type.eq(kind)].groupby("candidate_count").agg(selected=("homogeneous_normalized_selected_gain_mean","mean"),gap=("homogeneous_normalized_cross_fitted_gap_mean","mean")).reindex(ks)
            ax.plot(ks,part.selected,"o-",color=colors[pool],lw=1.25,ms=3.5); ax.plot(ks,part.gap,"o--",color=colors[pool],mfc="white",lw=1,ms=3.2)
        ax.axhline(0,color=GREY,lw=.7); ax.set_xticks(ks); ax.set_title(kind.title(),fontsize=9.2); ax.set_xlabel("K"); clean(ax)
        if idx==0: ax.set_ylabel("Normalized value")
    fig.text(gs[0,1].get_position(fig).x0,.975,"B  Composition-by-K ladder",fontsize=10.3,fontweight="bold",va="top")
    index=pd.MultiIndex.from_product([tasks,pools],names=["task","pool"])
    hit=base.pivot_table(index=["task","pool"],columns="candidate_count",values="chance_adjusted_hit3_mean").reindex(index)[ks]
    vals=hit.to_numpy(float); display=np.full((19,4),np.nan); rows=list(range(9))+list(range(10,19)); display[rows]=vals
    ax=fig.add_subplot(gs[1,0]); mesh=ax.pcolormesh(np.arange(5),np.arange(20),np.ma.masked_invalid(display),cmap="RdYlBu",vmin=-1,vmax=1,shading="flat")
    ax.set(xlim=(-.72,4),ylim=(19,0)); ax.set_xticks(np.arange(4)+.5,["4","8","16","32"])
    centres=[1.5,4.5,7.5,11.5,14.5,17.5]; ax.set_yticks(centres,[labels[t] for t in tasks],fontweight="bold")
    short={pools[0]:"H",pools[1]:"MV",pools[2]:"M"}
    for i,(task,pool) in enumerate(index):
        rp=rows[i]; ax.text(-.28,rp+.5,short[pool],ha="center",va="center",fontweight="bold",fontsize=8,color=colors[pool],clip_on=False)
        for j in range(4):
            rgba=mesh.cmap(mesh.norm(vals[i,j])); lum=.2126*rgba[0]+.7152*rgba[1]+.0722*rgba[2]
            ax.text(j+.5,rp+.5,f"{vals[i,j]:.2f}",ha="center",va="center",fontsize=8,color="white" if lum<.5 else "black")
    for s in ax.spines.values(): s.set_visible(False)
    ax.set_xlabel("Candidate-pool size, K"); ax.text(.5,1.005,"CAHit@3",transform=ax.transAxes,ha="center",va="bottom",fontsize=8.5,fontweight="bold")
    equal_k=units[units.design.eq("equal_K")&units.anchor_scheme.eq("shared_morgan_linear")].groupby(["pool","candidate_count"],as_index=False).agg(time=("audit_fit_seconds","mean"),gain=("homogeneous_normalized_selected_gain","mean"))
    equal_b=budget.groupby(["pool","candidate_count"],as_index=False).agg(time=("audit_fit_seconds","mean"),gain=("homogeneous_normalized_selected_gain","mean"))
    ax=fig.add_subplot(gs[1,1])
    for pool in pools:
        for tab,marker,ls in [(equal_k,"o","-"),(equal_b,"D","--")]:
            q=tab[tab.pool.eq(pool)].sort_values("candidate_count"); ax.plot(q.time,q.gain,color=colors[pool],ls=ls,lw=1.15); ax.scatter(q.time,q.gain,color=colors[pool],marker=marker,s=14+1.1*q.candidate_count,zorder=3)
    ax.set_xscale("log"); lo,hi=ax.get_xlim(); ticks=[x for x in [1,10,100,1000] if lo<=x<=hi]; ax.set_xticks(ticks); ax.set_xticklabels([str(x) for x in ticks]); ax.xaxis.set_minor_formatter(NullFormatter())
    ax.axhline(0,color=GREY,lw=.7); ax.set(xlabel="Downstream audit time (s, log scale)",ylabel="Normalized selected gain"); clean(ax,"both")
    handles=[Line2D([0],[0],color=colors[p],label=p31.POOL_SHORT[p]) for p in pools]+[Line2D([0],[0],color=INK,marker="o",label="Equal K"),Line2D([0],[0],color=INK,marker="D",ls="--",label="Equal budget")]
    ax.legend(handles=handles,frameon=False,ncol=2,fontsize=8,loc="best")
    y=gs[1,0].get_position(fig).y1+.018; fig.text(gs[1,0].get_position(fig).x0,y,"C  Ranking fidelity (CAHit@3)",fontsize=10.3,fontweight="bold",va="bottom"); fig.text(gs[1,1].get_position(fig).x0,y,"D  Downstream budget–benefit frontier",fontsize=10.3,fontweight="bold",va="bottom")
    (OUT/"Figure_7C_entropy_moved_to_Figure_S20.txt").write_text("The entropy column is omitted from main Figure 7C and retained in Supplementary Figure S20.",encoding="utf-8")
    save(fig,7)


def figure8():
    fixed=pd.read_csv(TABLES/"fixed_reference_units.csv"); tau=pd.read_csv(TABLES/"tau_near_equivalence_units.csv"); comp=pd.read_csv(TABLES/"classification_metric_selector_comparisons.csv")
    work=tau[((tau.task_type=="classification")&(tau.tau==.010))|((tau.task_type=="regression")&(tau.tau==.050))]
    fig=plt.figure(figsize=(6.69,6.25)); gs=fig.add_gridspec(2,2,left=.105,right=.985,bottom=.085,top=.90,hspace=.40,wspace=.34)
    asub=gs[0,0].subgridspec(2,1,hspace=.42); est=[("fixed_k32_gap","-","o","K-invariant"),("k_dependent_crossfit_gap","--","s","K-dependent"),("same_fold_opportunity_gap",":","^","Same-fold")]
    shared=[]
    for idx,(kind,color,title,ylabel) in enumerate([("classification",BLUE,"Classification","ROC-AUC gap"),("regression",ORANGE,"Regression","RMSE gap")]):
        ax=fig.add_subplot(asub[idx],sharex=shared[0] if shared else None); q=fixed[fixed.task_type.eq(kind)]
        for col,ls,m,_ in est:
            z=q.groupby("pool_size")[col].mean().reindex([4,8,16,32]); ax.plot(z.index,z,color=color,marker=m,ls=ls,lw=1.25,ms=4.1)
        ax.axhline(0,color=GREY,lw=.8); ax.set(ylabel=ylabel,xticks=[4,8,16,32]); ax.set_title(title,loc="left",pad=2,fontsize=9)
        if idx==0: ax.tick_params(axis="x",labelbottom=False)
        else: ax.set_xlabel("Candidate count, K")
        clean(ax); shared.append(ax)
    fig.text(.105,.972,"A  Reference and opportunity gaps",fontsize=10.3,fontweight="bold",va="top")
    fig.legend(handles=[Line2D([0],[0],color=INK,marker=m,ls=ls,label=lab) for _,ls,m,lab in est],loc="upper center",bbox_to_anchor=(.325,.952),ncol=3,frameon=False,fontsize=8)
    ax=fig.add_subplot(gs[0,1])
    for kind,lab,color,m in [("classification","Classification, τ = 0.010",BLUE,"o"),("regression","Regression, τ = 0.050",ORANGE,"s")]:
        z=work[work.task_type.eq(kind)].groupby("pool_size").crossfit_tau_success.mean().reindex([4,8,16,32]); ax.plot(z.index,100*z,marker=m,color=color,label=lab,lw=1.25,ms=4.2)
    ax.set(xlabel="Candidate count, K",ylabel="Cross-fitted τ-success (%)",xticks=[4,8,16,32],ylim=(0,100)); ax.set_title("B  Practical-equivalence success",loc="left",pad=5); ax.legend(frameon=False,loc="lower right"); clean(ax)
    ax=fig.add_subplot(gs[1,0])
    for kind,lab,color,m in [("classification","Classification, τ = 0.010",BLUE,"o"),("regression","Regression, τ = 0.050",ORANGE,"s")]:
        z=work[work.task_type.eq(kind)].groupby("pool_size").crossfit_near_equivalent_n.mean().reindex([4,8,16,32]); ax.plot(z.index,z,marker=m,color=color,label=lab,lw=1.25,ms=4.2)
    ax.set(xlabel="Candidate count, K",ylabel="Mean cross-fitted set size",xticks=[4,8,16,32]); ax.set_ylim(bottom=0); ax.set_title("C  Near-equivalent candidate sets",loc="left",pad=4); clean(ax)
    order=["bace","bbbp","clintox","tdc_hia_hou","tdc_pgp_broccatelli"]; k32=comp[comp.pool_size.eq(32)].groupby(["alternative_selector","dataset"]).mean(numeric_only=True)
    switch=np.column_stack([100*k32.loc[("pr_auc",),"candidate_changed_vs_roc"].reindex(order),100*k32.loc[("minority_constrained",),"candidate_changed_vs_roc"].reindex(order)])
    effect=np.column_stack([k32.loc[("pr_auc",),"delta_outer_pr_auc_vs_roc_selector"].reindex(order),k32.loc[("minority_constrained",),"delta_outer_minority_recall_vs_roc_selector"].reindex(order)])
    dsub=gs[1,1].subgridspec(1,2,wspace=.30)
    for idx,(arr,cols,cmap,lim,fmt,title) in enumerate([(switch,["PR-AUC\nswitch","Recall-rule\nswitch"],"Blues",(0,100),"{:.0f}%","D1  Candidate switching"),(effect,["ΔPR-AUC","Δminority\nrecall"],"RdBu_r",(-.04,.04),"{:+.3f}","D2  Outer performance change")]):
        ax=fig.add_subplot(dsub[idx]); mesh=ax.pcolormesh(np.arange(3),np.arange(6),arr,shading="flat",cmap=cmap,vmin=lim[0],vmax=lim[1]); ax.set(xlim=(0,2),ylim=(5,0)); ax.set_xticks([.5,1.5],cols); ax.set_yticks(np.arange(5)+.5,[DISPLAY[x] for x in order] if idx==0 else [])
        if idx==1: ax.tick_params(axis="y",left=False,labelleft=False)
        for i in range(5):
            for j in range(2):
                rgba=mesh.cmap(mesh.norm(arr[i,j])); lum=.2126*rgba[0]+.7152*rgba[1]+.0722*rgba[2]; ax.text(j+.5,i+.5,fmt.format(arr[i,j]),ha="center",va="center",fontsize=8,color="white" if lum<.5 else "black")
        for s in ax.spines.values(): s.set_visible(False)
        ax.set_title(title,loc="left",fontsize=9.2,pad=5)
    save(fig,8)


if __name__ == "__main__":
    setup(); OUT.mkdir(parents=True,exist_ok=True); figure1(); setup(); figure3(); setup(); figure7(); setup(); figure8(); print(OUT)
