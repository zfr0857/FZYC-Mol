from __future__ import annotations

import os
import shutil
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Circle, Rectangle, Arc
from mpl_toolkits.axes_grid1.inset_locator import inset_axes


ROOT = Path("D:/fzyc")
CORE = Path(os.environ.get("FZYC_CORE_OUT", ROOT / "output" / "paper20_candidate_pool_audit_20260712"))
NEW = Path(os.environ.get("FZYC_ANALYSIS_OUT", ROOT / "output" / "paper21_final_reanalysis_20260713"))
MINOR = Path(os.environ.get("FZYC_MINOR_OUT", ROOT / "output" / "paper23_minor_revision_20260713"))
MAJOR = ROOT / "output" / "paper19_major_revision_20260712"
PREV = ROOT / "output" / "paper19_rejection_driven_experiments_20260712"
REV = ROOT / "output" / "paper19_jcheminformatics_revision_20260712"
HARD = ROOT / "output" / "sci1_hardening_20260707"
FIG = Path(os.environ.get("FZYC_FIG_OUT", NEW / "main_figures"))
FINAL = Path(os.environ.get("FZYC_FINAL_OUT", FIG.parent))
SOURCE = FINAL / "figure_source_data"

BLUE, ORANGE, TEAL, PURPLE, GREY, RED = "#315E8A", "#D58135", "#2F8B83", "#78689A", "#7A7F87", "#B85C5C"
LIGHT, INK = "#E3E7EA", "#202830"
DISPLAY = {"bace":"BACE", "bbbp":"BBBP", "clintox":"ClinTox", "esol":"ESOL", "freesolv":"FreeSolv", "lipo":"Lipophilicity", "tdc_caco2_wang":"Caco2", "tdc_hia_hou":"HIA", "tdc_pgp_broccatelli":"P-gp"}


def setup():
    mpl.rcParams.update({"font.family":"Times New Roman", "font.serif":["Times New Roman"], "font.size":9.0,
        "mathtext.fontset":"stix", "axes.unicode_minus":False, "axes.titlesize":10.3, "axes.titleweight":"bold",
        "axes.labelsize":9.2, "xtick.labelsize":8.0, "ytick.labelsize":8.0, "legend.fontsize":8.2,
        "axes.linewidth":0.75, "lines.linewidth":1.25, "lines.markersize":5.0,
        "axes.spines.top":False, "axes.spines.right":False, "pdf.fonttype":42, "ps.fonttype":42, "svg.fonttype":"none",
        "savefig.facecolor":"white", "figure.facecolor":"white"})


def panel(ax, label, title, label_x=-0.13, title_x=0.0):
    ax.text(label_x, 1.08, label, transform=ax.transAxes, fontsize=12.0, fontweight="bold", va="top")
    ax.set_title(title, loc="left", x=title_x, pad=4)


def four_panel_grid(fig, *, left=.105, right=.98, bottom=.12, top=.93, hspace=.50, wspace=.42):
    """Return a balanced 2 x 2 journal layout used by Figures 4-6."""
    return fig.add_gridspec(2,2,left=left,right=right,bottom=bottom,top=top,hspace=hspace,wspace=wspace)


def save(fig, stem):
    FIG.mkdir(parents=True, exist_ok=True)
    pdf=FIG/f"{stem}.pdf"; png=FIG/f"{stem}.png"; svg=FIG/f"{stem}.svg"
    fig.savefig(pdf, bbox_inches="tight", facecolor="white")
    fig.savefig(png, dpi=600, bbox_inches="tight", facecolor="white")
    fig.savefig(svg, bbox_inches="tight", facecolor="white")
    number=int(stem.split("_")[1])
    shutil.copy2(pdf,FIG/f"Figure{number}.pdf")
    shutil.copy2(svg,FIG/f"Figure{number}.svg")
    shutil.copy2(png,FIG/f"Figure{number}_600dpi.png")
    plt.close(fig)


def _figure1_text_rich_reference():
    fig,ax=plt.subplots(figsize=(7.2,4.30)); ax.set_xlim(0,1); ax.set_ylim(0,1); ax.axis("off")
    pale={BLUE:"#EAF1F7",TEAL:"#E7F2EF",ORANGE:"#FBE9DD",PURPLE:"#EEEAF5"}

    def group(x,y,w,h,title,color=INK,fill="white"):
        ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle="round,pad=.006,rounding_size=.012",fc=fill,ec=INK,lw=.8,linestyle=(0,(2,2))))
        ax.text(x+w/2,y+h-.018,title,ha="center",va="top",fontsize=8.2,fontweight="bold",color=color)

    def arrow(x1,y1,x2,y2,color=GREY,scale=7,lw=.8):
        ax.add_patch(FancyArrowPatch((x1,y1),(x2,y2),arrowstyle="-|>",mutation_scale=scale,lw=lw,color=color))

    # Three reference-style workflow bands.
    ax.text(.011,.835,"REGISTRATION",rotation=90,ha="center",va="center",fontsize=8.0,fontweight="bold",color=INK)
    ax.text(.011,.535,"NESTED AUDIT",rotation=90,ha="center",va="center",fontsize=8.0,fontweight="bold",color=INK)
    ax.text(.011,.240,"DECOMPOSITION & REPORTING",rotation=90,ha="center",va="center",fontsize=8.0,fontweight="bold",color=INK)

    group(.035,.700,.430,.275,"Study and candidate registration",BLUE)
    cards=[("Task","9 endpoints",BLUE),("Dataset","public data",BLUE),("Representation","molecular\nviews",TEAL),("Candidate","learners +\nsettings",ORANGE)]
    for i,(header,detail,color) in enumerate(cards):
        x=.055+i*.100
        ax.add_patch(FancyBboxPatch((x,.750),.083,.145,boxstyle="round,pad=.004,rounding_size=.009",fc=pale[color],ec="none"))
        if i==0:
            ax.add_patch(Circle((x+.0415,.855),.016,fc="white",ec=color,lw=.8)); ax.plot([x+.032,x+.0415,x+.052],[.850,.866,.849],color=color,lw=.8)
        elif i==1:
            for j,w in enumerate([.047,.040,.033]): ax.add_patch(Rectangle((x+.018,.868-j*.013),w,.008,fc="white",ec=color,lw=.7))
        elif i==2:
            for rr in range(2):
                for cc in range(4): ax.add_patch(Rectangle((x+.020+cc*.012,.844+rr*.015),.009,.010,fc=color if (rr+cc)%2==0 else "white",ec=color,lw=.55))
        else:
            for j in range(3): ax.add_patch(FancyBboxPatch((x+.020+j*.007,.840+j*.010),.043,.028,boxstyle="round,pad=.001",fc="white",ec=color,lw=.7))
        ax.text(x+.0415,.807,header,ha="center",va="center",fontsize=8.0,fontweight="bold",color=INK)
        ax.text(x+.0415,.771,detail,ha="center",va="center",fontsize=8.0,color=GREY)
        if i<3: arrow(x+.084,.822,x+.097,.822,scale=6)

    group(.490,.700,.495,.275,"Registered candidate-pool construction",ORANGE)
    pool_x=[.535,.645,.755,.875]
    for i,(x,k) in enumerate(zip(pool_x,[4,8,16,32])):
        for j in range(i+1):
            ax.add_patch(FancyBboxPatch((x-.021+j*.007,.822+j*.007),.044,.036,boxstyle="round,pad=.001",fc="white",ec=[BLUE,TEAL,ORANGE,PURPLE][j%4],lw=.75))
        ax.text(x+.004,.785,f"K = {k}",ha="center",va="center",fontsize=8.0,fontweight="bold",color=PURPLE)
        if i<3: arrow(x+.042,.840,pool_x[i+1]-.040,.840,scale=6)
    ax.text(.737,.735,"Prespecified prefixes  |  random and family-balanced controls",ha="center",va="center",fontsize=8.0,color=GREY)

    arrow(.250,.696,.250,.676,scale=10,lw=1.2); arrow(.740,.696,.740,.676,scale=10,lw=1.2)
    group(.035,.395,.430,.275,"Repeated nested model selection",BLUE)
    nested=[(.055,.480,.073,"5 split\nseeds",BLUE),(.150,.480,.080,"3 outer\nscaffold folds",TEAL),(.252,.480,.074,"3 inner\nfolds",TEAL),(.348,.466,.096,"Fold-specific\npreprocessing\n+ ranking",ORANGE)]
    for i,(x,y,w,label,color) in enumerate(nested):
        ax.add_patch(FancyBboxPatch((x,y),w,.112 if i<3 else .140,boxstyle="round,pad=.004,rounding_size=.008",fc=pale[color],ec=color,lw=.75))
        if i==0:
            for j in range(3): ax.add_patch(Rectangle((x+.016+j*.012,y+.074+j*.004),.030,.015,fc="white",ec=color,lw=.6))
        elif i in (1,2):
            for j in range(3): ax.add_patch(Circle((x+.020+j*.020,y+.084),.008,fc="white",ec=color,lw=.65))
        ax.text(x+w/2,y+.040 if i<3 else y+.052,label,ha="center",va="center",fontsize=8.0,color=INK)
        if i<len(nested)-1: arrow(x+w+.003,.538,nested[i+1][0]-.004,.538,scale=6)
    ax.text(.250,.425,"All preprocessing and selection are fitted inside the training hierarchy",ha="center",va="center",fontsize=8.0,color=GREY)

    group(.490,.395,.495,.275,"Outer audit and cross-fitted reference",TEAL)
    audit=[(.512,.485,.086,"Selected\ncandidate",ORANGE),(.620,.485,.078,"Candidate\nrefit",ORANGE),(.720,.485,.092,"Untouched\nouter fold",BLUE),(.835,.485,.126,"Audit outcome\n+ cross-fitted\nreference",PURPLE)]
    for i,(x,y,w,label,color) in enumerate(audit):
        ax.add_patch(FancyBboxPatch((x,y),w,.112,boxstyle="round,pad=.004,rounding_size=.008",fc=pale[color],ec=color,lw=.75))
        ax.text(x+w/2,y+.056,label,ha="center",va="center",fontsize=8.0,color=INK)
        if i<len(audit)-1: arrow(x+w+.003,.541,audit[i+1][0]-.004,.541,scale=6)
    ax.add_patch(FancyBboxPatch((.585,.420),.305,.038,boxstyle="round,pad=.002,rounding_size=.005",fc=pale[TEAL],ec=TEAL,lw=.75))
    ax.add_patch(FancyBboxPatch((.602,.429),.015,.014,boxstyle="round,pad=.001",fc="white",ec=TEAL,lw=.65)); ax.add_patch(Arc((.6095,.444),.013,.015,theta1=0,theta2=180,color=TEAL,lw=.65))
    ax.text(.746,.439,"No outer-label feedback",ha="center",va="center",fontsize=8.0,fontweight="bold",color=TEAL)

    arrow(.178,.391,.178,.366,scale=10,lw=1.2); arrow(.505,.391,.505,.366,scale=10,lw=1.2); arrow(.842,.391,.842,.366,scale=10,lw=1.2)
    group(.035,.115,.285,.245,"Diversity and ranking audit",PURPLE)
    for rr in range(4):
        for cc in range(4):
            shade=mpl.colors.to_rgba(PURPLE,alpha=.18+.11*abs(rr-cc))
            ax.add_patch(Rectangle((.058+cc*.026,.180+rr*.026),.024,.024,fc=shade,ec="white",lw=.50))
    arrow(.170,.228,.195,.228,scale=6)
    ax.text(.205,.240,"Matrix-dependent\ndiversity",ha="left",va="center",fontsize=8.0,color=INK)
    ax.text(.205,.184,"Chance-adjusted\nranking",ha="left",va="center",fontsize=8.0,color=INK)

    group(.335,.115,.335,.245,"Selection-gap decomposition",PURPLE)
    ax.text(.355,.274,"Validation-selected",ha="left",va="center",fontsize=8.0,color=GREY)
    ax.plot([.475,.570],[.274,.274],color=LIGHT,lw=1.4); ax.scatter([.475,.570],[.274,.274],s=20,color=[TEAL,BLUE],zorder=3)
    ax.text(.582,.274,"audit-best",ha="left",va="center",fontsize=8.0,color=GREY)
    ax.text(.355,.201,"Same-unit",ha="left",va="center",fontsize=8.0,color=GREY)
    ax.plot([.440,.548],[.201,.201],color=LIGHT,lw=1.4); ax.scatter([.440,.548],[.201,.201],s=20,marker="s",color=[BLUE,TEAL],zorder=3)
    ax.text(.560,.201,"cross-fitted",ha="left",va="center",fontsize=8.0,color=GREY)
    ax.text(.503,.145,"Endpoint loss  |  winner optimism",ha="center",va="center",fontsize=8.0,fontweight="bold",color=PURPLE)

    group(.685,.115,.300,.245,"Composition and reliability",TEAL)
    for j in range(3): ax.add_patch(FancyBboxPatch((.710+j*.008,.236+j*.008),.050,.037,boxstyle="round,pad=.001",fc="white",ec=ORANGE,lw=.7))
    ax.text(.748,.190,"Matched-size\nsubset effects",ha="center",va="center",fontsize=8.0,color=INK)
    arrow(.785,.236,.812,.236,scale=6)
    heat=np.array([[.90,.55,.18],[.78,.43,.12],[.64,.35,.08]])
    for rr in range(3):
        for cc in range(3): ax.add_patch(Rectangle((.824+cc*.030,.225+rr*.027),.028,.025,fc=mpl.cm.RdYlGn(heat[rr,cc]),ec="white",lw=.50))
    ax.text(.868,.190,"Chemical-support\nrisk boundary",ha="center",va="center",fontsize=8.0,color=INK)

    phases=["Registration","Candidate\nexpansion","Nested\nselection","Outer audit","Statistical\ndecomposition","Reporting"]
    xs=np.linspace(.055,.945,len(phases)); ax.add_patch(FancyArrowPatch((.035,.070),(.975,.070),arrowstyle="-|>",mutation_scale=10,lw=1.5,color=GREY))
    for x,label in zip(xs,phases): ax.text(x,.052,label,ha="center",va="top",fontsize=8.0,color=INK)
    fig.subplots_adjust(.008,.015,.995,.995); save(fig,"Figure_1_retrospective_nested_audit_architecture")


def _figure1_single_row_graphic():
    fig,ax=plt.subplots(figsize=(7.2,3.05)); ax.set_xlim(0,1); ax.set_ylim(0,1); ax.axis("off")
    pale={BLUE:"#EAF1F7",TEAL:"#E7F2EF",ORANGE:"#FBE9DD",PURPLE:"#EEEAF5"}

    def stage(x,w,label,number,color):
        ax.add_patch(FancyBboxPatch((x,.205),w,.685,boxstyle="round,pad=.006,rounding_size=.013",fc="white",ec=INK,lw=.8,linestyle=(0,(2,2))))
        ax.add_patch(FancyBboxPatch((x+.008,.805),w-.016,.067,boxstyle="round,pad=.002,rounding_size=.010",fc=pale[color],ec="none"))
        ax.add_patch(Circle((x+.027,.838),.017,fc=color,ec="white",lw=.6))
        ax.text(x+.027,.838,str(number),ha="center",va="center",fontsize=8.0,fontweight="bold",color="white")
        ax.text(x+.052,.838,label,ha="left",va="center",fontsize=7.5,fontweight="bold",color=color)

    def arrow(x1,y1,x2,y2,color=GREY,scale=7,lw=.9):
        ax.add_patch(FancyArrowPatch((x1,y1),(x2,y2),arrowstyle="-|>",mutation_scale=scale,lw=lw,color=color))

    ax.text(.50,.965,"Retrospective nested audit",ha="center",va="top",fontsize=9.0,fontweight="bold",color=INK)
    stage(.025,.155,"REGISTER",1,BLUE); stage(.205,.155,"EXPAND",2,ORANGE); stage(.385,.165,"NESTED CV",3,TEAL); stage(.575,.165,"OUTER AUDIT",4,BLUE); stage(.765,.210,"DIAGNOSE",5,PURPLE)
    for x1,x2 in [(.180,.205),(.360,.385),(.550,.575),(.740,.765)]: arrow(x1+.003,.555,x2-.003,.555,scale=8,lw=1.0)

    # 1 | Molecular tasks, datasets and endpoint registry.
    cx,cy,r=.071,.665,.036; theta=np.linspace(0,2*np.pi,7); hx=cx+r*np.cos(theta); hy=cy+r*np.sin(theta)
    ax.plot(hx,hy,color=BLUE,lw=1.0)
    ax.scatter(hx[:-1],hy[:-1],s=11,fc="white",ec=BLUE,lw=.65,zorder=3)
    ax.plot([cx+r,cx+r+.026],[cy,cy+.030],color=TEAL,lw=.9); ax.scatter([cx+r+.026],[cy+.030],s=12,fc=TEAL,ec="white",lw=.55,zorder=3)
    arrow(.112,.665,.132,.665,scale=6)
    for j in range(3): ax.add_patch(Rectangle((.125+j*.005,.620+j*.018),.036,.054,fc="white",ec=BLUE,lw=.65))
    ax.plot([.052,.150],[.515,.515],color=LIGHT,lw=1.0)
    ax.scatter([.059,.082,.105,.128,.150],[.493,.543,.510,.560,.525],s=17,color=[BLUE,TEAL,ORANGE,PURPLE,BLUE],zorder=3)
    ax.text(.102,.303,"9 endpoints",ha="center",va="center",fontsize=8.0,fontweight="bold",color=BLUE)

    # 2 | Registered pool expansion represented as growing candidate stacks.
    stack_specs=[(.235,.665,4),(.307,.665,8),(.235,.465,16),(.307,.465,32)]
    family_colors=[BLUE,TEAL,ORANGE,PURPLE]
    for index,(cx,cy,k) in enumerate(stack_specs):
        layers=index+1
        for j in range(layers): ax.add_patch(FancyBboxPatch((cx-.023+j*.006,cy-.018+j*.008),.046,.036,boxstyle="round,pad=.001",fc="white",ec=family_colors[j%4],lw=.65))
        ax.text(cx+.008,cy-.060,f"K = {k}",ha="center",va="center",fontsize=8.0,fontweight="bold",color=PURPLE)
    ax.scatter([.240,.270,.300,.330],[.302]*4,s=23,color=family_colors,edgecolors="white",linewidths=.55)

    # 3 | Seeded nested scaffold folds, fold-wise preprocessing and ranking.
    seed_y=np.linspace(.685,.565,5); ax.scatter([.407]*5,seed_y,s=18,color=[BLUE,TEAL,ORANGE,PURPLE,BLUE],edgecolors="white",linewidths=.55)
    arrow(.420,.625,.440,.625,scale=6)
    for j in range(3): ax.add_patch(FancyBboxPatch((.437+j*.010,.470+j*.012),.086,.205,boxstyle="round,pad=.002",fc="white",ec=TEAL,lw=.70))
    for j in range(3): ax.add_patch(FancyBboxPatch((.460+j*.007,.515+j*.010),.045,.105,boxstyle="round,pad=.001",fc=pale[ORANGE],ec=ORANGE,lw=.65))
    ax.add_patch(mpl.patches.Polygon([[.448,.414],[.519,.414],[.495,.372],[.495,.342],[.472,.342],[.472,.372]],closed=True,fc=pale[BLUE],ec=BLUE,lw=.65))
    for j,h in enumerate([.022,.038,.055,.073]): ax.add_patch(Rectangle((.514+j*.007,.342),.005,h,fc=PURPLE,ec=PURPLE,lw=.55))
    ax.text(.468,.292,"5 seeds",ha="center",va="center",fontsize=8.0,color=TEAL,fontweight="bold")
    ax.text(.468,.252,"3 outer  |  3 inner",ha="center",va="center",fontsize=8.0,color=TEAL,fontweight="bold")

    # 4 | Locked outer-fold audit and cross-fitted reference construction.
    rank_y=[.700,.640,.580,.520]; rank_x=[.606,.632,.650,.620]
    for y,x,c in zip(rank_y,rank_x,[GREY,ORANGE,BLUE,TEAL]):
        ax.plot([.596,.663],[y,y],color=LIGHT,lw=1.0); ax.scatter([x],[y],s=20,color=c,zorder=3)
    ax.add_patch(Circle((.632,.640),.019,fc="none",ec=ORANGE,lw=1.0))
    arrow(.666,.610,.689,.610,scale=6)
    shield=mpl.patches.Polygon([[.692,.690],[.723,.678],[.721,.605],[.708,.560],[.695,.605]],closed=True,fc=pale[BLUE],ec=BLUE,lw=.8)
    ax.add_patch(shield); ax.plot([.700,.706,.716],[.625,.614,.646],color=BLUE,lw=1.0)
    fold_x=[.597,.626,.655]
    for i,x in enumerate(fold_x): ax.add_patch(Rectangle((x,.392),.024,.052,fc="white",ec=[BLUE,TEAL,PURPLE][i],lw=.65))
    ax.add_patch(Arc((.636,.420),.104,.110,theta1=20,theta2=160,color=GREY,lw=.75)); arrow(.586,.438,.586,.421,scale=5,lw=.75)
    ax.add_patch(Arc((.636,.420),.104,.110,theta1=200,theta2=340,color=GREY,lw=.75)); arrow(.686,.400,.686,.418,scale=5,lw=.75)
    ax.text(.658,.332,"cross-fit",ha="center",va="center",fontsize=8.0,color=PURPLE,fontweight="bold")
    ax.add_patch(FancyBboxPatch((.594,.246),.127,.046,boxstyle="round,pad=.002,rounding_size=.006",fc=pale[TEAL],ec=TEAL,lw=.65))
    ax.text(.658,.269,"No label feedback",ha="center",va="center",fontsize=8.0,fontweight="bold",color=TEAL)

    # 5 | Three graphical audit outputs converge on the report.
    for rr in range(4):
        for cc in range(4): ax.add_patch(Rectangle((.781+cc*.014,.575+rr*.014),.012,.012,fc=mpl.colors.to_rgba(PURPLE,.18+.10*abs(rr-cc)),ec="white",lw=.50))
    ax.text(.802,.525,"Diversity",ha="center",va="center",fontsize=8.0,color=PURPLE,fontweight="bold")
    ax.axvline(.870,ymin=.57,ymax=.72,color=INK,lw=.65)
    for y,lo,mid,hi,c in [(.622,.842,.862,.889,BLUE),(.649,.850,.875,.898,TEAL),(.676,.838,.868,.892,ORANGE)]:
        ax.plot([lo,hi],[y,y],color=GREY,lw=.75); ax.scatter([mid],[y],s=15,color=c,zorder=3)
    ax.text(.870,.525,"Gap",ha="center",va="center",fontsize=8.0,color=PURPLE,fontweight="bold")
    risk=np.array([[.90,.55,.18],[.78,.43,.12],[.64,.35,.08]])
    for rr in range(3):
        for cc in range(3): ax.add_patch(Rectangle((.923+cc*.016,.600+rr*.018),.014,.016,fc=mpl.cm.RdYlGn(risk[rr,cc]),ec="white",lw=.50))
    ax.text(.947,.525,"Support",ha="center",va="center",fontsize=8.0,color=TEAL,fontweight="bold")
    for x,c in [(.802,PURPLE),(.870,BLUE),(.947,TEAL)]: arrow(x,.497,.873,.405,color=c,scale=5,lw=.7)
    ax.add_patch(Rectangle((.840,.305),.066,.090,fc="white",ec=INK,lw=.7))
    ax.add_patch(Rectangle((.890,.371),.016,.024,fc=pale[ORANGE],ec=ORANGE,lw=.55))
    for j,w in enumerate([.043,.050,.036]): ax.plot([.851,.851+w],[.367-j*.018,.367-j*.018],color=GREY,lw=.7)
    ax.text(.873,.267,"Report",ha="center",va="center",fontsize=8.0,fontweight="bold",color=INK)

    # A graphic-only process spine reinforces the one-way audit sequence.
    centers=[.1025,.2825,.4675,.6575,.870]; ax.plot([.055,.945],[.145,.145],color=LIGHT,lw=1.5)
    ax.scatter(centers,[.145]*5,s=25,color=[BLUE,ORANGE,TEAL,BLUE,PURPLE],edgecolors="white",linewidths=.6,zorder=3); arrow(.940,.145,.970,.145,scale=8,lw=1.1)
    fig.subplots_adjust(.008,.015,.995,.995); save(fig,"Figure_1_retrospective_nested_audit_architecture")


def _figure1_three_row_reference():
    fig,ax=plt.subplots(figsize=(7.2,4.10)); ax.set_xlim(0,1); ax.set_ylim(0,1); ax.axis("off")
    pale={BLUE:"#EAF1F7",TEAL:"#E7F2EF",ORANGE:"#FBE9DD",PURPLE:"#EEEAF5"}

    def group(x,y,w,h,title,color):
        ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle="round,pad=.006,rounding_size=.012",fc="white",ec=INK,lw=.8,linestyle=(0,(2,2))))
        ax.text(x+w/2,y+h-.015,title,ha="center",va="top",fontsize=7.8,fontweight="bold",color=color)

    def arrow(x1,y1,x2,y2,color=GREY,scale=7,lw=.8):
        ax.add_patch(FancyArrowPatch((x1,y1),(x2,y2),arrowstyle="-|>",mutation_scale=scale,lw=lw,color=color))

    ax.text(.012,.835,"INPUT",rotation=90,ha="center",va="center",fontsize=8.0,fontweight="bold",color=INK)
    ax.text(.012,.535,"NESTED AUDIT",rotation=90,ha="center",va="center",fontsize=8.0,fontweight="bold",color=INK)
    ax.text(.012,.245,"ANALYSIS",rotation=90,ha="center",va="center",fontsize=8.0,fontweight="bold",color=INK)

    # Top row: registered study objects flow into the prespecified candidate pools.
    group(.035,.700,.440,.275,"DATA & REGISTRY",BLUE)
    cx,cy,r=.079,.825,.032; theta=np.linspace(0,2*np.pi,7); hx=cx+r*np.cos(theta); hy=cy+r*np.sin(theta)
    ax.plot(hx,hy,color=BLUE,lw=.9); ax.scatter(hx[:-1],hy[:-1],s=10,fc="white",ec=BLUE,lw=.60,zorder=3)
    ax.plot([cx+r,cx+r+.020],[cy,cy+.022],color=TEAL,lw=.8); ax.scatter([cx+r+.020],[cy+.022],s=11,fc=TEAL,ec="white",lw=.55,zorder=3)
    arrow(.122,.825,.151,.825,scale=6)
    for j in range(3): ax.add_patch(Rectangle((.153+j*.006,.788+j*.016),.047,.060,fc="white",ec=BLUE,lw=.60))
    arrow(.211,.825,.240,.825,scale=6)
    for rr in range(2):
        for cc in range(4): ax.add_patch(Rectangle((.249+cc*.018,.803+rr*.025),.014,.018,fc=[BLUE,TEAL,ORANGE,PURPLE][cc],ec="white",lw=.50))
    arrow(.329,.825,.359,.825,scale=6)
    ax.add_patch(Circle((.402,.825),.040,fc=pale[ORANGE],ec=ORANGE,lw=.70)); ax.plot([.379,.397,.425],[.818,.843,.808],color=ORANGE,lw=1.0)
    ax.scatter([.379,.397,.425],[.818,.843,.808],s=10,color=ORANGE,zorder=3)
    for x,label in zip([.079,.177,.285,.402],["molecules","datasets","views","9 endpoints"]): ax.text(x,.746,label,ha="center",va="center",fontsize=8.0,color=INK)

    group(.495,.700,.490,.275,"CANDIDATE POOL",ORANGE)
    nodes=[(.528,.850,BLUE),(.550,.875,TEAL),(.572,.850,ORANGE),(.550,.817,PURPLE)]
    for x,y,c in nodes: ax.scatter([x],[y],s=19,color=c,edgecolors="white",linewidths=.55,zorder=3)
    for i in range(len(nodes)):
        for j in range(i+1,len(nodes)): ax.plot([nodes[i][0],nodes[j][0]],[nodes[i][1],nodes[j][1]],color=LIGHT,lw=.6,zorder=1)
    arrow(.590,.845,.615,.845,scale=6)
    pool_x=[.642,.735,.827,.920]
    for i,(x,k) in enumerate(zip(pool_x,[4,8,16,32])):
        for j in range(i+1): ax.add_patch(FancyBboxPatch((x-.020+j*.006,.823+j*.007),.040,.032,boxstyle="round,pad=.001",fc="white",ec=[BLUE,TEAL,ORANGE,PURPLE][j%4],lw=.60))
        ax.text(x+.004,.765,f"K = {k}",ha="center",va="center",fontsize=8.0,fontweight="bold",color=PURPLE)
        if i<3: arrow(x+.030,.842,pool_x[i+1]-.029,.842,scale=5)
    ax.scatter([.680,.730,.780,.830],[.722]*4,s=18,color=[BLUE,TEAL,ORANGE,PURPLE],edgecolors="white",linewidths=.50)

    arrow(.255,.696,.255,.674,scale=9,lw=1.1); arrow(.740,.696,.740,.674,scale=9,lw=1.1)

    # Middle row: every frame contains a complete input-to-output audit subflow.
    group(.035,.405,.440,.260,"NESTED SELECTION",TEAL)
    seed_y=np.linspace(.585,.495,5); ax.scatter([.066]*5,seed_y,s=17,color=[BLUE,TEAL,ORANGE,PURPLE,BLUE],edgecolors="white",linewidths=.5)
    ax.text(.066,.443,"5 seeds",ha="center",va="center",fontsize=8.0,fontweight="bold",color=BLUE); arrow(.080,.540,.114,.540,scale=6)
    for j in range(3): ax.add_patch(FancyBboxPatch((.114+j*.009,.485+j*.010),.073,.112,boxstyle="round,pad=.002",fc="white",ec=TEAL,lw=.65))
    ax.text(.157,.443,"3 outer",ha="center",va="center",fontsize=8.0,fontweight="bold",color=TEAL); arrow(.205,.540,.236,.540,scale=6)
    for j in range(3): ax.add_patch(FancyBboxPatch((.236+j*.008,.505+j*.009),.061,.087,boxstyle="round,pad=.002",fc=pale[ORANGE],ec=ORANGE,lw=.65))
    ax.text(.270,.443,"3 inner",ha="center",va="center",fontsize=8.0,fontweight="bold",color=ORANGE); arrow(.316,.540,.344,.540,scale=6)
    ax.add_patch(mpl.patches.Polygon([[.345,.584],[.403,.584],[.383,.548],[.383,.515],[.365,.515],[.365,.548]],closed=True,fc=pale[BLUE],ec=BLUE,lw=.65))
    for j,h in enumerate([.023,.039,.057,.074]): ax.add_patch(Rectangle((.407+j*.009,.500),.006,h,fc=PURPLE,ec=PURPLE,lw=.55))
    ax.text(.389,.443,"rank",ha="center",va="center",fontsize=8.0,fontweight="bold",color=PURPLE)

    group(.495,.405,.490,.260,"OUTER AUDIT",BLUE)
    rank_y=[.586,.548,.510,.472]; rank_x=[.520,.543,.562,.532]
    for y,x,c in zip(rank_y,rank_x,[GREY,ORANGE,BLUE,TEAL]): ax.plot([.510,.572],[y,y],color=LIGHT,lw=.8); ax.scatter([x],[y],s=16,color=c,zorder=3)
    ax.add_patch(Circle((.543,.548),.015,fc="none",ec=ORANGE,lw=.9)); arrow(.575,.535,.602,.535,scale=6)
    for j in range(3): ax.add_patch(FancyBboxPatch((.603+j*.006,.509+j*.008),.044,.052,boxstyle="round,pad=.001",fc="white",ec=ORANGE,lw=.60))
    arrow(.658,.535,.683,.535,scale=6)
    shield=mpl.patches.Polygon([[.687,.588],[.727,.578],[.724,.508],[.707,.468],[.690,.508]],closed=True,fc=pale[BLUE],ec=BLUE,lw=.75); ax.add_patch(shield); ax.plot([.698,.705,.717],[.533,.521,.552],color=BLUE,lw=.9)
    arrow(.733,.535,.758,.535,scale=6)
    fold_x=[.772,.811,.850]
    for i,x in enumerate(fold_x): ax.add_patch(Rectangle((x,.510),.031,.057,fc="white",ec=[BLUE,TEAL,PURPLE][i],lw=.60))
    ax.add_patch(Arc((.826,.537),.135,.130,theta1=20,theta2=160,color=GREY,lw=.7)); arrow(.760,.556,.760,.536,scale=5,lw=.7)
    ax.add_patch(Arc((.826,.537),.135,.130,theta1=200,theta2=340,color=GREY,lw=.7)); arrow(.891,.517,.891,.537,scale=5,lw=.7)
    arrow(.904,.535,.930,.535,scale=6)
    ax.add_patch(Rectangle((.934,.500),.031,.073,fc="white",ec=PURPLE,lw=.65)); ax.plot([.940,.958],[.552,.552],color=PURPLE,lw=.65); ax.plot([.940,.958],[.535,.535],color=PURPLE,lw=.65)
    ax.add_patch(FancyBboxPatch((.637,.425),.205,.039,boxstyle="round,pad=.002,rounding_size=.006",fc=pale[TEAL],ec=TEAL,lw=.60)); ax.text(.739,.444,"No label feedback",ha="center",va="center",fontsize=8.0,fontweight="bold",color=TEAL)

    arrow(.178,.401,.178,.376,scale=9,lw=1.1); arrow(.505,.401,.505,.376,scale=9,lw=1.1); arrow(.842,.401,.842,.376,scale=9,lw=1.1)

    # Bottom row: compact statistical workflows rather than prose descriptions.
    group(.035,.120,.285,.250,"DIVERSITY",PURPLE)
    for rr in range(4):
        for cc in range(4): ax.add_patch(Rectangle((.062+cc*.026,.200+rr*.026),.023,.023,fc=mpl.colors.to_rgba(PURPLE,.18+.10*abs(rr-cc)),ec="white",lw=.50))
    arrow(.176,.246,.202,.246,scale=6)
    ax.plot([.215,.215],[.190,.305],color=INK,lw=.60); ax.plot([.215,.290],[.190,.190],color=INK,lw=.60)
    for i,(x,y,c) in enumerate([(.231,.223,BLUE),(.249,.250,TEAL),(.267,.275,ORANGE),(.285,.293,PURPLE)]): ax.plot([x,x],[.190,y],color=c,lw=2.2)
    ax.text(.252,.150,"matrix  →  rank",ha="center",va="center",fontsize=8.0,fontweight="bold",color=PURPLE)

    group(.335,.120,.335,.250,"SELECTION GAP",PURPLE)
    ax.text(.359,.282,"selected",ha="left",va="center",fontsize=8.0,color=GREY); ax.plot([.440,.555],[.282,.282],color=LIGHT,lw=1.2); ax.scatter([.450,.545],[.282,.282],s=18,color=[TEAL,BLUE],zorder=3); arrow(.560,.282,.594,.282,scale=5)
    ax.text(.359,.205,"same",ha="left",va="center",fontsize=8.0,color=GREY); ax.plot([.423,.538],[.205,.205],color=LIGHT,lw=1.2); ax.scatter([.438,.525],[.205,.205],s=18,marker="s",color=[BLUE,TEAL],zorder=3); arrow(.543,.205,.577,.205,scale=5)
    ax.scatter([.612,.612],[.282,.205],s=22,color=[ORANGE,PURPLE],zorder=3); ax.text(.503,.150,"audit-best  |  cross-fit",ha="center",va="center",fontsize=8.0,fontweight="bold",color=PURPLE)

    group(.685,.120,.300,.250,"RELIABILITY",TEAL)
    for j in range(3): ax.add_patch(FancyBboxPatch((.709+j*.007,.238+j*.008),.045,.034,boxstyle="round,pad=.001",fc="white",ec=ORANGE,lw=.60))
    ax.text(.735,.184,"K = 3",ha="center",va="center",fontsize=8.0,fontweight="bold",color=ORANGE); arrow(.770,.250,.803,.250,scale=6)
    risk=np.array([[.90,.55,.18],[.78,.43,.12],[.64,.35,.08]])
    for rr in range(3):
        for cc in range(3): ax.add_patch(Rectangle((.810+cc*.025,.220+rr*.025),.023,.023,fc=mpl.cm.RdYlGn(risk[rr,cc]),ec="white",lw=.50))
    arrow(.895,.250,.920,.250,scale=6)
    ax.add_patch(Rectangle((.927,.208),.043,.085,fc="white",ec=INK,lw=.65)); ax.add_patch(Rectangle((.958,.272),.012,.021,fc=pale[ORANGE],ec=ORANGE,lw=.50)); ax.plot([.935,.959],[.264,.264],color=GREY,lw=.60); ax.plot([.935,.959],[.244,.244],color=GREY,lw=.60); ax.plot([.935,.953],[.224,.224],color=GREY,lw=.60)
    ax.text(.850,.150,"support  →  report",ha="center",va="center",fontsize=8.0,fontweight="bold",color=TEAL)

    phases=["Register","Expand","Select","Audit","Decompose","Report"]; xs=np.linspace(.060,.940,len(phases)); ax.add_patch(FancyArrowPatch((.035,.070),(.975,.070),arrowstyle="-|>",mutation_scale=9,lw=1.4,color=GREY))
    for x,label in zip(xs,phases): ax.text(x,.048,label,ha="center",va="top",fontsize=8.0,color=INK)
    fig.subplots_adjust(.008,.015,.995,.995); save(fig,"Figure_1_retrospective_nested_audit_architecture")


def _figure1_literature_informed_four_scene():
    fig,ax=plt.subplots(figsize=(7.2,3.55)); ax.set_xlim(0,1); ax.set_ylim(0,1); ax.axis("off")
    pale={BLUE:"#EAF1F7",TEAL:"#E7F2EF",ORANGE:"#FBE9DD",PURPLE:"#EEEAF5"}

    def stage(x,w,title,number,color):
        ax.add_patch(FancyBboxPatch((x,.105),w,.815,boxstyle="round,pad=.008,rounding_size=.025",fc=pale[color],ec="none"))
        ax.add_patch(Circle((x+.024,.875),.017,fc=color,ec="white",lw=.7,zorder=4))
        ax.text(x+.024,.875,str(number),ha="center",va="center",fontsize=8.0,fontweight="bold",color="white",zorder=5)
        title_size=7.0 if title=="REGISTERED EVIDENCE" else 7.5
        ax.text(x+.050,.875,title,ha="left",va="center",fontsize=title_size,fontweight="bold",color=color)

    def arrow(x1,y1,x2,y2,color=GREY,scale=8,lw=.9,rad=0):
        ax.add_patch(FancyArrowPatch((x1,y1),(x2,y2),arrowstyle="-|>",mutation_scale=scale,lw=lw,color=color,
                                     connectionstyle=f"arc3,rad={rad}"))

    stage(.025,.200,"REGISTERED EVIDENCE",1,BLUE)
    stage(.245,.210,"CANDIDATE UNIVERSE",2,ORANGE)
    stage(.475,.230,"NESTED AUDIT",3,TEAL)
    stage(.725,.250,"EVIDENCE MAP",4,PURPLE)
    for x1,x2 in [(.225,.245),(.455,.475),(.705,.725)]: arrow(x1+.002,.535,x2-.002,.535,scale=9,lw=1.15)

    # 1 | Literal chemical objects and a compact registered endpoint map.
    cx,cy,r=.079,.635,.040; theta=np.linspace(0,2*np.pi,7); hx=cx+r*np.cos(theta); hy=cy+r*np.sin(theta)
    ax.plot(hx,hy,color=BLUE,lw=1.15); ax.scatter(hx[:-1],hy[:-1],s=15,fc="white",ec=BLUE,lw=.7,zorder=3)
    ax.plot([cx+r,cx+r+.026],[cy,cy+.032],color=TEAL,lw=1.0)
    ax.scatter([cx+r+.026],[cy+.032],s=18,fc=TEAL,ec="white",lw=.6,zorder=3)
    arrow(.130,.635,.151,.635,scale=6)
    endpoint_colors=[BLUE,TEAL,ORANGE,PURPLE,BLUE,TEAL,ORANGE,PURPLE,BLUE]
    for i,c in enumerate(endpoint_colors):
        rr,cc=divmod(i,3); x=.160+cc*.018; y=.670-rr*.043
        ax.scatter([x],[y],s=23,color=c,edgecolors="white",linewidths=.55,zorder=3)
        if cc<2: ax.plot([x,x+.018],[y,y],color="white",lw=.7,zorder=2)
    for j in range(3):
        ax.add_patch(FancyBboxPatch((.060+j*.007,.347+j*.010),.105,.115,boxstyle="round,pad=.002,rounding_size=.007",fc="white",ec=BLUE,lw=.65))
    for j,w in enumerate([.063,.075,.050]): ax.plot([.077,.077+w],[.429-j*.026,.429-j*.026],color=LIGHT,lw=1.3)
    ax.add_patch(Circle((.169,.390),.022,fc=pale[TEAL],ec=TEAL,lw=.7)); ax.plot([.158,.167,.181],[.389,.380,.402],color=TEAL,lw=1.2)
    ax.text(.120,.252,"9 endpoints",ha="center",va="center",fontsize=8.0,fontweight="bold",color=BLUE)

    # 2 | A family-coloured graph fan makes pool expansion visible without enumerating models.
    ax.add_patch(Circle((.270,.535),.022,fc=ORANGE,ec="white",lw=.7,zorder=4))
    family_colors=[BLUE,TEAL,ORANGE,PURPLE]
    candidate_nodes=[]
    row_spec=[(.710,4),(.600,5),(.490,6),(.380,7)]
    for row,(y,n) in enumerate(row_spec):
        xs=np.linspace(.305,.405,n)
        ax.plot([.270,xs[0]],[.535,y],color=mpl.colors.to_rgba(GREY,.55),lw=.75,zorder=1)
        for j,x in enumerate(xs):
            c=family_colors[(j+row)%4]; candidate_nodes.append((x,y,c))
            if j: ax.plot([xs[j-1],x],[y,y],color=mpl.colors.to_rgba(GREY,.35),lw=.65,zorder=1)
            ax.scatter([x],[y],s=20 if row<2 else 17,color=c,edgecolors="white",linewidths=.5,zorder=3)
        ax.text(.432,y,f"K = {[4,8,16,32][row]}",ha="center",va="center",fontsize=8.0,fontweight="bold",color=PURPLE)
    ax.add_patch(Arc((.354,.545),.195,.455,theta1=72,theta2=288,color=mpl.colors.to_rgba(ORANGE,.50),lw=.8))
    ax.text(.345,.252,"prespecified growth",ha="center",va="center",fontsize=8.0,color=ORANGE,fontweight="bold")

    # 3 | Seeded outer and inner scaffold folds are shown as nested audit rings.
    seed_x=np.linspace(.520,.652,5)
    ax.scatter(seed_x,[.727]*5,s=22,color=[BLUE,TEAL,ORANGE,PURPLE,BLUE],edgecolors="white",linewidths=.55,zorder=3)
    ax.text(.586,.775,"5 seeds",ha="center",va="center",fontsize=8.0,fontweight="bold",color=BLUE)
    for lo,hi,c in [(8,112,TEAL),(128,232,"#46A59B"),(248,352,"#25766F")]:
        ax.add_patch(Arc((.586,.548),.148,.270,theta1=lo,theta2=hi,color=c,lw=6.0,capstyle="round"))
    for lo,hi,c in [(12,108,ORANGE),(132,228,"#E29A5B"),(252,348,"#BD6B29")]:
        ax.add_patch(Arc((.586,.548),.090,.165,theta1=lo,theta2=hi,color=c,lw=4.3,capstyle="round"))
    for j,h in enumerate([.026,.044,.062,.082]): ax.add_patch(Rectangle((.559+j*.014,.507),.009,h,fc=PURPLE,ec="white",lw=.50,zorder=4))
    arrow(.665,.548,.677,.548,color=BLUE,scale=6,lw=.9)
    shield=mpl.patches.Polygon([[.678,.604],[.696,.596],[.695,.534],[.687,.503],[.679,.534]],closed=True,fc="white",ec=BLUE,lw=.85)
    ax.add_patch(shield); ax.plot([.682,.687,.693],[.554,.544,.572],color=BLUE,lw=1.0)
    ax.text(.586,.330,"3 outer  |  3 inner",ha="center",va="center",fontsize=8.0,fontweight="bold",color=TEAL)
    ax.add_patch(FancyBboxPatch((.500,.210),.180,.057,boxstyle="round,pad=.002,rounding_size=.009",fc="white",ec=TEAL,lw=.65))
    ax.add_patch(Rectangle((.514,.228),.014,.016,fc="white",ec=TEAL,lw=.65)); ax.add_patch(Arc((.521,.244),.012,.015,theta1=0,theta2=180,color=TEAL,lw=.65))
    ax.text(.607,.239,"No outer-label feedback",ha="center",va="center",fontsize=8.0,fontweight="bold",color=TEAL)

    # 4 | Three compact experimental signatures converge on one auditable report.
    for rr in range(4):
        for cc in range(4):
            ax.add_patch(Rectangle((.750+cc*.018,.615+rr*.023),.016,.020,
                                   fc=mpl.colors.to_rgba(PURPLE,.17+.11*abs(rr-cc)),ec="white",lw=.50))
    ax.text(.777,.575,"diversity",ha="center",va="center",fontsize=8.0,fontweight="bold",color=PURPLE)
    for y,lo,mid,hi,c in [(.690,.845,.865,.889,BLUE),(.655,.837,.873,.900,TEAL),(.620,.852,.884,.910,ORANGE)]:
        ax.plot([lo,hi],[y,y],color=LIGHT,lw=1.4); ax.scatter([mid],[y],s=20,color=c,zorder=3)
    ax.plot([.875,.875],[.605,.706],color=INK,lw=.6)
    ax.text(.875,.575,"selection gap",ha="center",va="center",fontsize=8.0,fontweight="bold",color=PURPLE)
    risk=np.array([[.90,.55,.18],[.78,.43,.12],[.64,.35,.08]])
    for rr in range(3):
        for cc in range(3): ax.add_patch(Rectangle((.751+cc*.023,.337+rr*.028),.021,.025,fc=mpl.cm.RdYlGn(risk[rr,cc]),ec="white",lw=.50))
    for j in range(3): ax.add_patch(FancyBboxPatch((.746+j*.005,.443+j*.007),.050,.035,boxstyle="round,pad=.001",fc="white",ec=ORANGE,lw=.55))
    ax.text(.780,.292,"support",ha="center",va="center",fontsize=8.0,fontweight="bold",color=TEAL)
    arrow(.797,.638,.895,.454,color=PURPLE,scale=5,lw=.65,rad=-.12)
    arrow(.908,.635,.924,.465,color=BLUE,scale=5,lw=.65,rad=.08)
    arrow(.818,.392,.884,.402,color=TEAL,scale=5,lw=.65,rad=-.08)
    ax.add_patch(Rectangle((.885,.348),.065,.105,fc="white",ec=INK,lw=.75))
    ax.add_patch(Rectangle((.936,.429),.014,.024,fc=pale[ORANGE],ec=ORANGE,lw=.50))
    for j,w in enumerate([.040,.045,.032]): ax.plot([.896,.896+w],[.425-j*.024,.425-j*.024],color=GREY,lw=.75)
    ax.text(.918,.292,"report",ha="center",va="center",fontsize=8.0,fontweight="bold",color=INK)

    # A sparse spine reinforces the one-way research logic without repeating the caption.
    ax.plot([.060,.940],[.055,.055],color=LIGHT,lw=1.5)
    centers=[.120,.345,.590,.850]
    ax.scatter(centers,[.055]*4,s=28,color=[BLUE,ORANGE,TEAL,PURPLE],edgecolors="white",linewidths=.6,zorder=3)
    arrow(.935,.055,.970,.055,scale=8,lw=1.0)
    fig.subplots_adjust(.006,.012,.996,.995); save(fig,"Figure_1_retrospective_nested_audit_architecture")


def _figure1_central_audit_map():
    fig,ax=plt.subplots(figsize=(7.2,4.05)); ax.set_xlim(0,1); ax.set_ylim(0,1); ax.axis("off")
    brick="#A95A52"; support="#6E9D80"; dark="#30383F"
    pale={BLUE:"#EDF3F8",ORANGE:"#FCF0E5",TEAL:"#EAF4F1",PURPLE:"#F1EEF7",brick:"#F7ECEA",support:"#EDF5EF"}

    def box(x,y,w,h,title,color,letter,fill="white"):
        ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle="round,pad=.004,rounding_size=.010",fc=fill,ec=color,lw=.65))
        badge_x,badge_y=x+.018,y+h-.032
        ax.add_patch(mpl.patches.Ellipse((badge_x,badge_y),.030,.052,fc=color,ec="white",lw=.55,zorder=4))
        ax.text(badge_x,badge_y,letter,ha="center",va="center",fontsize=10.2,fontweight="bold",color="white",zorder=5)
        multiline="\n" in title
        title_y=y+h-(.032 if multiline else .020)
        ax.text(x+.034,title_y,title,ha="left",va="center",fontsize=8.5 if multiline else 9.0,
                fontweight="bold",color=color,linespacing=1.25)

    def arrow(x1,y1,x2,y2,color=GREY,lw=.65,scale=6,rad=0,style="-|>"):
        ax.add_patch(FancyArrowPatch((x1,y1),(x2,y2),arrowstyle=style,mutation_scale=scale,lw=lw,color=color,
                                     connectionstyle=f"arc3,rad={rad}"))

    def molecule(cx,cy,r,color=BLUE,sub=True):
        t=np.linspace(0,2*np.pi,7); x=cx+r*np.cos(t); y=cy+r*np.sin(t)
        ax.plot(x,y,color=color,lw=.75); ax.scatter(x[:-1],y[:-1],s=7,fc="white",ec=color,lw=.55,zorder=3)
        if sub:
            ax.plot([cx+r,cx+r*1.42],[cy,cy+r*.58],color=color,lw=.7)
            ax.scatter([cx+r*1.42],[cy+r*.58],s=8,fc=TEAL,ec="white",lw=.5,zorder=3)

    def mini_matrix(x,y,n=3,size=.009,color=PURPLE,mode=0):
        for rr in range(n):
            for cc in range(n):
                if mode==0: a=.18+.13*abs(rr-cc)
                elif mode==1: a=.20+.11*((rr+cc)%3)
                elif mode==2: a=.18+.12*cc
                else: a=.18+.12*rr
                ax.add_patch(Rectangle((x+cc*size,y+rr*size),size*.90,size*.90,fc=mpl.colors.to_rgba(color,a),ec="white",lw=.50))

    ax.text(.5,.990,"Retrospective Nested Audit of Candidate-Pool Expansion and Model-Selection Loss",
            ha="center",va="top",fontsize=9.0,fontweight="bold",color=dark)

    # Twelve balanced modules around the central audit core.
    box(.018,.705,.250,.245,"Task and Data Registration",BLUE,"A",pale[BLUE])
    box(.018,.445,.250,.245,"Candidate Pool\nExpansion",ORANGE,"B",pale[ORANGE])
    box(.285,.365,.360,.585,"Repeated Nested Scaffold Audit",TEAL,"C",pale[TEAL])
    box(.665,.735,.160,.215,"Utility-Pattern\nDiversity",PURPLE,"D",pale[PURPLE])
    box(.665,.510,.160,.210,"Chance-Adjusted\nRanking",PURPLE,"E",pale[PURPLE])
    box(.385,.065,.260,.280,"Selection-Gap Decomposition\nand Cross-Fitting",brick,"F",pale[brick])
    box(.018,.065,.145,.360,"Split-Regime\nTransfer",ORANGE,"G",pale[ORANGE])
    box(.173,.065,.202,.280,"Equal-Size Registry\nComposition",TEAL,"H",pale[TEAL])
    box(.665,.285,.160,.210,"Winner-Selection\nOptimism",brick,"I",pale[brick])
    box(.840,.510,.142,.440,"Support-Aware\nReliability",support,"J",pale[support])
    box(.665,.065,.160,.200,"Four-Model\nError Audit",BLUE,"K",pale[BLUE])
    box(.840,.065,.142,.430,"Auditable\nEvidence Map",PURPLE,"L",pale[PURPLE])

    # Structural arrows: inputs feed the core; analytical branches surround it; evidence converges rightward.
    arrow(.268,.815,.285,.785,BLUE,lw=.8,scale=7); arrow(.268,.565,.285,.610,ORANGE,lw=.8,scale=7)
    arrow(.645,.825,.665,.835,PURPLE,lw=.75,scale=7); arrow(.645,.690,.665,.615,PURPLE,lw=.75,scale=7)
    arrow(.535,.365,.535,.345,brick,lw=.75,scale=7); arrow(.645,.520,.665,.390,brick,lw=.7,scale=6)
    arrow(.825,.840,.840,.835,PURPLE,lw=.75,scale=7); arrow(.825,.615,.840,.660,PURPLE,lw=.75,scale=7)
    arrow(.825,.390,.840,.420,brick,lw=.75,scale=7); arrow(.825,.165,.840,.260,BLUE,lw=.75,scale=7)

    # A | Public endpoints, deterministic molecular cleaning and scaffold partitions.
    molecule(.050,.850,.020,BLUE)
    for j in range(3): ax.add_patch(Rectangle((.076+j*.004,.820+j*.010),.040,.052,fc="white",ec=BLUE,lw=.55))
    ax.text(.132,.850,"9 endpoints",ha="left",va="center",fontsize=8.0,fontweight="bold",color=BLUE)
    ax.text(.030,.818,"Reg: ESOL · FreeSolv · Lipo · Caco2",ha="left",va="center",fontsize=7.0,color=ORANGE)
    ax.text(.030,.792,"Class: BBBP · BACE · ClinTox",ha="left",va="center",fontsize=7.0,color=BLUE)
    ax.text(.030,.766,"HIA · P-gp",ha="left",va="center",fontsize=7.0,color=BLUE)
    ax.text(.030,.740,"SMILES  →  RDKit  →  curated",ha="left",va="center",fontsize=7.0,color=dark)
    ax.text(.030,.713,"seeded scaffold folds · no overlap",ha="left",va="center",fontsize=7.0,fontweight="bold",color=TEAL)

    # B | Shared Morgan representation and prespecified nested candidate prefixes.
    for rr in range(4):
        for cc in range(4): ax.add_patch(Rectangle((.035+cc*.009,.594+rr*.010),.008,.009,fc=[BLUE,TEAL,ORANGE,PURPLE][(rr+cc)%4],ec="white",lw=.50))
    ax.text(.060,.578,"Morgan-512",ha="center",va="center",fontsize=8.0,fontweight="bold",color=BLUE)
    ax.add_patch(Circle((.092,.606),.012,fc=ORANGE,ec="white",lw=.55,zorder=3))
    pool_rows=[(.625,4,"o"),(.587,8,"s"),(.549,16,"^"),(.511,32,"D")]
    for row,(y,k,marker) in enumerate(pool_rows):
        arrow(.103,.606,.126,y,ORANGE,lw=.55,scale=5)
        xs=np.linspace(.133,.198,3+row)
        ax.plot(xs,[y]*len(xs),color=LIGHT,lw=.8)
        ax.scatter(xs,[y]*len(xs),s=12,marker=marker,color=[BLUE,TEAL,ORANGE,PURPLE][:len(xs)] if len(xs)<=4 else PURPLE,
                   edgecolors="white",linewidths=.5,zorder=3)
        ax.text(.250,y,f"K={k}",ha="right",va="center",fontsize=8.0,fontweight="bold",color=PURPLE)
    ax.text(.030,.488,"fixed order · no reordering",ha="left",va="center",fontsize=8.0,color=dark)
    ax.add_patch(Rectangle((.204,.455),.018,.014,fc="white",ec=ORANGE,lw=.55)); ax.plot([.208,.218],[.462,.462],color=ORANGE,lw=.6)
    ax.text(.030,.456,"17,280 fits  |  4,437.95 s",ha="left",va="center",fontsize=8.0,fontweight="bold",color=ORANGE)

    # C | Three nested audit rings, frozen selector, one-shot outer evaluation and shielded separation.
    cx,cy=.445,.655
    seed_angles=np.linspace(25,335,5)
    for ang,c in zip(seed_angles,[BLUE,TEAL,ORANGE,PURPLE,BLUE]):
        rad=np.deg2rad(ang); ax.scatter([cx+.125*np.cos(rad)],[cy+.185*np.sin(rad)],s=16,color=c,edgecolors="white",linewidths=.55,zorder=5)
    for lo,hi,c in [(8,112,TEAL),(128,232,"#49A89E"),(248,352,"#25766F")]:
        ax.add_patch(Arc((cx,cy),.245,.365,theta1=lo,theta2=hi,color=c,lw=5.7,capstyle="round"))
    for lo,hi,c in [(10,110,ORANGE),(130,230,"#E39A57"),(250,350,"#BC6B29")]:
        ax.add_patch(Arc((cx,cy),.165,.245,theta1=lo,theta2=hi,color=c,lw=4.2,capstyle="round"))
    for lo,hi,c in [(15,105,PURPLE),(135,225,"#8B7AAF"),(255,345,"#655387")]:
        ax.add_patch(Arc((cx,cy),.095,.140,theta1=lo,theta2=hi,color=c,lw=3.0,capstyle="round"))
    for j,h in enumerate([.018,.032,.048,.064]): ax.add_patch(Rectangle((cx-.035+j*.019,cy-.034),.011,h,fc=PURPLE,ec="white",lw=.50,zorder=5))
    ax.text(.445,.876,"5 seeds: 11 · 23 · 37 · 53 · 71",ha="center",va="center",fontsize=8.0,fontweight="bold",color=BLUE)
    ax.text(.445,.795,"3 outer folds",ha="center",va="center",fontsize=8.0,fontweight="bold",color=TEAL)
    ax.text(.445,.748,"3 inner folds",ha="center",va="center",fontsize=8.0,fontweight="bold",color=ORANGE)
    ax.text(.445,.584,"ROC-AUC  |  −RMSE",ha="center",va="center",fontsize=8.0,fontweight="bold",color=PURPLE,
            bbox=dict(boxstyle="round,pad=.18",fc=pale[TEAL],ec="none"))
    arrow(.505,.655,.545,.655,TEAL,lw=.8,scale=7)
    ax.add_patch(FancyBboxPatch((.548,.625),.055,.060,boxstyle="round,pad=.002",fc="white",ec=TEAL,lw=.65,zorder=6))
    ax.add_patch(Rectangle((.565,.650),.018,.015,fc="white",ec=TEAL,lw=.6,zorder=7)); ax.add_patch(Arc((.574,.666),.015,.017,theta1=0,theta2=180,color=TEAL,lw=.6,zorder=7))
    ax.text(.575,.638,"Freeze",ha="center",va="center",fontsize=8.0,fontweight="bold",color=TEAL,zorder=7)
    arrow(.605,.655,.625,.655,BLUE,lw=.75,scale=6)
    ax.add_patch(Rectangle((.616,.605),.020,.095,fc="white",ec=BLUE,lw=.65)); ax.plot([.620,.632],[.675,.675],color=BLUE,lw=.6); ax.plot([.620,.632],[.650,.650],color=BLUE,lw=.6)
    ax.add_patch(FancyBboxPatch((.535,.525),.102,.070,boxstyle="round,pad=.002,rounding_size=.006",fc="white",ec=LIGHT,lw=.55,zorder=6))
    ax.text(.586,.575,"Outer refit",ha="center",va="center",fontsize=8.0,color=dark,zorder=7)
    ax.text(.586,.542,"One-shot test",ha="center",va="center",fontsize=8.0,color=dark,zorder=7)
    shield=mpl.patches.Polygon([[.500,.520],[.530,.511],[.528,.448],[.515,.415],[.502,.448]],closed=True,fc="white",ec=TEAL,lw=.75,zorder=6)
    ax.add_patch(shield); ax.plot([.507,.514,.524],[.466,.454,.484],color=TEAL,lw=.9,zorder=7)
    ax.add_patch(FancyBboxPatch((.532,.392),.108,.126,boxstyle="round,pad=.002,rounding_size=.006",fc="white",ec=TEAL,lw=.55,zorder=6))
    ax.text(.586,.485,"Outer labels\nshielded",ha="center",va="center",fontsize=7.7,fontweight="bold",color=TEAL,linespacing=1.18,zorder=7)
    ax.text(.588,.445,"No test tuning",ha="center",va="center",fontsize=8.0,color=dark,zorder=7)
    ax.text(.588,.417,"In-fold fitting",ha="center",va="center",fontsize=8.0,color=dark,zorder=7)
    ax.text(.445,.382,"selection inside  |  audit outside",ha="center",va="center",fontsize=8.0,fontweight="bold",color=dark)

    # D | Matrix transformations and effective-rank spectrum.
    for i,(lab,mode) in enumerate(zip(["Raw","Ctr","Ref","Rank"],range(4))):
        x=.678+i*.033; mini_matrix(x,.810,3,.008,PURPLE,mode); ax.text(x+.011,.792,lab,ha="center",va="center",fontsize=8.0,color=dark)
    wave_x=np.linspace(.678,.798,30); ax.plot(wave_x,.873+.010*np.sin(np.linspace(0,3*np.pi,30)),color=GREY,lw=.65)
    for j,h in enumerate([.012,.020,.028,.036]): ax.add_patch(Rectangle((.680+j*.012,.748),.008,h,fc=PURPLE,ec="white",lw=.50))
    ax.text(.770,.752,"K ≠ rank",ha="center",va="center",fontsize=8.0,fontweight="bold",color=PURPLE)

    # E | Ranking swaps remain structured as K expands.
    top=[.548,.570,.592,.614]; bot=[.554,.606,.578,.626]
    for x in top: ax.scatter([.684],[x],s=11,color=BLUE,edgecolors="white",linewidths=.5,zorder=3)
    for x in bot: ax.scatter([.735],[x],s=11,color=ORANGE,edgecolors="white",linewidths=.5,zorder=3)
    for a,b in zip(top,bot): ax.plot([.687,.732],[a,b],color=GREY,lw=.55)
    ax.text(.684,.530,"K=4",ha="center",va="center",fontsize=8.0,fontweight="bold",color=BLUE); ax.text(.735,.530,"K=32",ha="center",va="center",fontsize=8.0,fontweight="bold",color=ORANGE)
    for i,lab in enumerate(["CAHit@3","MRR","NDCG","ρ / τ"]):
        cy=.645-i*.038
        ax.add_patch(FancyBboxPatch((.752,cy-.019),.068,.038,boxstyle="round,pad=.001",fc="white",ec=PURPLE,lw=.55))
        ax.text(.786,cy,lab,ha="center",va="center",fontsize=7.4,color=PURPLE)

    # F | Same-unit versus cross-fitted references and heterogeneous endpoint effects.
    ax.text(.400,.265,"selected",ha="left",va="center",fontsize=8.0,color=TEAL); ax.text(.400,.230,"audit-best",ha="left",va="center",fontsize=8.0,color=brick)
    ax.plot([.458,.520],[.265,.265],color=LIGHT,lw=1.2); ax.scatter([.468,.509],[.265,.265],s=14,color=[TEAL,brick],zorder=3)
    ax.plot([.458,.520],[.230,.230],color=LIGHT,lw=1.2); ax.scatter([.473,.514],[.230,.230],s=14,marker="s",color=[BLUE,PURPLE],zorder=3)
    ax.text(.490,.203,"selection loss",ha="center",va="center",fontsize=8.0,fontweight="bold",color=brick)
    ax.add_patch(Arc((.425,.153),.050,.055,theta1=20,theta2=330,color=brick,lw=.65)); arrow(.447,.135,.451,.153,brick,lw=.55,scale=4)
    ax.text(.455,.155,"same-unit",ha="left",va="center",fontsize=8.0,color=brick)
    ax.scatter(np.linspace(.405,.455,4),[.103]*4,s=10,color=[BLUE,TEAL,ORANGE,PURPLE],zorder=3)
    arrow(.462,.103,.500,.103,TEAL,lw=.6,scale=5); ax.add_patch(Rectangle((.503,.090),.025,.026,fc="white",ec=TEAL,lw=.55)); arrow(.532,.103,.560,.103,TEAL,lw=.6,scale=5); ax.scatter([.566],[.103],s=14,fc="white",ec=TEAL,lw=.65)
    ax.text(.475,.078,"cross-fit reference",ha="center",va="center",fontsize=8.0,color=TEAL)
    ax.plot([.585,.585],[.100,.275],color=INK,lw=.55)
    for y,lo,mid,hi,c in [(.255,.595,.610,.628,BLUE),(.225,.602,.620,.638,ORANGE),(.195,.592,.605,.622,BLUE),(.165,.607,.626,.641,ORANGE),(.135,.596,.615,.633,BLUE)]:
        ax.plot([lo,hi],[y,y],color=GREY,lw=.6); ax.scatter([mid],[y],s=10,color=c,zorder=3)
    ax.axvline(.615,ymin=.34,ymax=.80,color=LIGHT,lw=.65,linestyle=(0,(2,2)))
    ax.text(.595,.115,"heterogeneous",ha="center",va="center",fontsize=8.0,fontweight="bold",color=brick)
    ax.text(.595,.083,"not universal",ha="center",va="center",fontsize=8.0,fontweight="bold",color=brick)

    # G | The same audit is transferred from scaffold to stricter similarity-component separation.
    route_y=[.320,.245]; labels=["Scaffold","Similarity"]
    for y,lab,m in zip(route_y,labels,["o","s"]):
        ax.text(.030,y,lab,ha="left",va="center",fontsize=8.0,color=dark)
        xs=np.linspace(.080,.124,4); ax.plot(xs,[y]*4,color=LIGHT,lw=.8)
        ax.scatter(xs,[y]*4,s=15,marker=m,color=ORANGE,edgecolors="white",linewidths=.5,zorder=3)
    arrow(.090,.205,.090,.155,ORANGE,lw=.75,scale=5)
    ax.text(.090,.122,"direction\ntransfer",ha="center",va="center",fontsize=8.0,fontweight="bold",color=ORANGE)

    # H | Fixed K isolates registry composition across homogeneous, multiview and modern-augmented pools.
    pool_rows=[(.255,"Morgan",PURPLE),(.190,"Multiview",TEAL),(.125,"Modern+",ORANGE)]
    for y,lab,c in pool_rows:
        mini_matrix(.195,y,2,.009,c,0)
        ax.text(.222,y+.009,lab,ha="left",va="center",fontsize=8.0,color=dark)
        ax.scatter([.310,.340],[y+.009,y+.009],s=[16,28],marker="o",color=c,edgecolors="white",linewidths=.5)
    ax.text(.325,.078,"K=16     K=32",ha="center",va="center",fontsize=8.0,fontweight="bold",color=PURPLE)

    # I | Known-truth heatmap isolates finite-audit winner optimism.
    vals=np.array([[.20,.32,.48,.65],[.15,.26,.40,.58],[.10,.18,.31,.49],[.06,.12,.23,.38]])
    for rr in range(4):
        for cc in range(4): ax.add_patch(Rectangle((.682+cc*.025,.340+rr*.026),.022,.023,fc=mpl.cm.OrRd(.18+.72*vals[rr,cc]),ec="white",lw=.50))
    ax.text(.728,.326,"K: 4   8   16   32",ha="center",va="center",fontsize=8.0,color=dark)
    ax.text(.788,.392,"K ↑",ha="left",va="center",fontsize=8.0,fontweight="bold",color=brick)
    ax.text(.788,.363,"n ↓",ha="left",va="center",fontsize=8.0,fontweight="bold",color=brick)
    ax.text(.788,.334,"ρ ↓",ha="left",va="center",fontsize=8.0,fontweight="bold",color=brick)
    ax.text(.745,.295,"known-truth only",ha="center",va="center",fontsize=8.0,fontweight="bold",color=brick)

    # J | Chemical-support strata show increasing reliability toward related scaffolds.
    band_x=[.854,.894,.934]; band_c=["#F8E8E3","#EEF1D8","#D7EAD9"]
    for x,c in zip(band_x,band_c): ax.add_patch(Rectangle((x,.610),.037,.215,fc=c,ec="white",lw=.50))
    for i,x in enumerate(band_x): molecule(x+.018,.760-i*.030,.010,support,False)
    ax.text(.872,.842,"<0.5",ha="center",va="center",fontsize=8.0,fontweight="bold",color=brick)
    ax.text(.912,.842,"0.5–0.7",ha="center",va="center",fontsize=8.0,fontweight="bold",color=GREY)
    ax.text(.952,.842,"≥0.7",ha="center",va="center",fontsize=8.0,fontweight="bold",color=support)
    ax.text(.872,.585,"novel",ha="center",va="center",fontsize=8.0,color=brick); ax.text(.952,.585,"related",ha="center",va="center",fontsize=8.0,color=support)
    for x,c in [(.861,brick),(.910,ORANGE),(.960,brick)]: ax.scatter([x],[.552],s=11,color=c,zorder=3)
    ax.text(.911,.528,"Err ↑   Dis ↑   FN ↑",ha="center",va="center",fontsize=8.0,fontweight="bold",color=brick)

    # K | Four fixed models feed complementary prediction/error and reliability views.
    model_x=[.681,.721,.761,.801]
    for x,lab,m in zip(model_x,["RF","GCN","CBT","MFM"],["o","s","^","D"]):
        ax.scatter([x],[.204],s=14,marker=m,color=BLUE,edgecolors="white",linewidths=.5); ax.text(x,.187,lab,ha="center",va="center",fontsize=8.0,color=dark)
    for rr in range(4):
        for cc in range(4): ax.add_patch(Rectangle((.680+cc*.015,.120+rr*.015),.014,.014,fc=mpl.colors.to_rgba(BLUE if rr>cc else PURPLE,.18+.12*abs(rr-cc)),ec="white",lw=.50))
    ax.axvline(.790,ymin=.18,ymax=.58,color=GREY,lw=.55,linestyle=(0,(2,2)))
    for i,v in enumerate([.772,.800,.783,.807]): ax.scatter([v],[.130+i*.017],s=8,color=[BLUE,ORANGE,TEAL,PURPLE][i],zorder=3)

    # L | Six auditable evidence streams converge on a transparent report card.
    evidence=[("eligibility",BLUE),("K + pools",ORANGE),("diversity",PURPLE),("ranking",PURPLE),("selection gaps",brick),("support",support)]
    rail_y=[]
    for i,(lab,c) in enumerate(evidence):
        y=.420-i*.036; rail_y.append(y); ax.scatter([.855],[y],s=10,color=c,edgecolors="white",linewidths=.5,zorder=3); ax.text(.865,y,lab,ha="left",va="center",fontsize=8.0,color=dark); ax.plot([.963,.970],[y,y],color=c,lw=.55)
    ax.plot([.970,.970],[min(rail_y),max(rail_y)],color=GREY,lw=.60)
    arrow(.970,min(rail_y),.970,.204,PURPLE,lw=.65,scale=5)
    ax.add_patch(FancyBboxPatch((.849,.068),.124,.148,boxstyle="round,pad=.003,rounding_size=.007",fc="white",ec=PURPLE,lw=.70))
    ax.text(.911,.188,"Audit record",ha="center",va="center",fontsize=7.8,fontweight="bold",color=PURPLE)
    ax.text(.911,.148,"hashes · failures",ha="center",va="center",fontsize=7.3,color=dark)
    ax.text(.911,.110,"exposure",ha="center",va="center",fontsize=7.2,color=dark)
    ax.text(.911,.080,"uncertainty",ha="center",va="center",fontsize=7.2,color=dark)

    # Bottom conclusion strip, wrapped for full-size journal readability.
    ax.add_patch(FancyBboxPatch((.018,.008),.964,.047,boxstyle="round,pad=.002,rounding_size=.008",fc="#F4F5F5",ec=LIGHT,lw=.55))
    ax.text(.500,.031,"Candidate-pool expansion provides representation opportunity while increasing selection pressure;\nits effect is heterogeneous across endpoints and depends on chemical support.",
            ha="center",va="center",fontsize=8.0,fontweight="bold",color=dark,linespacing=1.10)

    fig.subplots_adjust(0,0,1,1)
    FIG.mkdir(parents=True,exist_ok=True)
    fig.savefig(FIG/"Figure1_4K.png",dpi=533.34,facecolor="white",bbox_inches=None,pad_inches=0)
    save(fig,"Figure_1_retrospective_nested_audit_architecture")


def figure1():
    return _figure1_central_audit_map()


def figure2():
    d=pd.read_csv(NEW/"effective_rank_bootstrap_5000_summary.csv")
    d=d[d.reference_label.eq("candidate_1")]
    loo=pd.read_csv(NEW/"effective_rank_leave_one_out.csv")
    refs=pd.read_csv(NEW/"effective_rank_reference_sensitivity.csv")
    fig=plt.figure(figsize=(7.2,5.35)); gs=fig.add_gridspec(2,2,width_ratios=[.92,1.08],wspace=.38,hspace=.44)
    axs=np.asarray([[fig.add_subplot(gs[0,0]),fig.add_subplot(gs[0,1])],[fig.add_subplot(gs[1,0]),fig.add_subplot(gs[1,1])]])
    mode_rows=[("raw",BLUE,"Raw"),("row_centred",ORANGE,"Row-centred"),("fixed_reference_relative",TEAL,"Fixed-reference"),("within_unit_rank",PURPLE,"Within-unit rank")]
    ax=axs[0,0]; panel(ax,"A","Effective diversity across K")
    legend_handles=[]
    for mode,c,label in mode_rows:
        q=(d[d.transformation.eq(mode)].groupby("candidate_count")["ledoit_wolf_entropy_rank"]
           .agg(y="median",lo=lambda x:x.quantile(.25),hi=lambda x:x.quantile(.75)).reset_index())
        line,=ax.plot(q.candidate_count,q.y,"o-",color=c,label=label,lw=1.5,ms=4.8); ax.fill_between(q.candidate_count,q.lo,q.hi,color=c,alpha=.07)
        legend_handles.append(line)
    nominal,=ax.plot([4,32],[4,32],":",color=GREY,label="Nominal K",lw=1.0)
    ax.set(xlabel="Nominal candidate count, K",ylabel="Entropy rank",xticks=[4,8,16,32])
    ax.text(.98,.14,"Common difficulty retained",transform=ax.transAxes,ha="right",va="bottom",fontsize=7.5,color=BLUE,bbox=dict(fc="white",ec="none",alpha=.82,pad=1.2))
    ax.text(.98,.42,"Common difficulty removed",transform=ax.transAxes,ha="right",va="bottom",fontsize=7.5,color=ORANGE,bbox=dict(fc="white",ec="none",alpha=.82,pad=1.2))
    ax=axs[0,1]; panel(ax,"B","Entropy and participation-ratio concordance")
    q=d[d.candidate_count.eq(32)];
    for mode,c,_ in mode_rows:
        z=q[q.transformation.eq(mode)]; ax.scatter(z.ledoit_wolf_entropy_rank,z.ledoit_wolf_participation_rank,color=c,s=34,edgecolors="white",linewidths=.5)
    lim=[1,max(q.ledoit_wolf_entropy_rank.max(),q.ledoit_wolf_participation_rank.max())*1.04]; ax.plot(lim,lim,":",color=GREY,lw=1.0)
    ax.set(xlabel="Entropy rank",ylabel="Participation-ratio rank")
    ax=axs[1,0]; panel(ax,"C","Candidate correlation after adjustment")
    for mode,c,_ in mode_rows:
        z=d[d.transformation.eq(mode)].groupby("candidate_count").ledoit_wolf_median_correlation.median(); ax.plot(z.index,z.values,"o-",color=c,ms=4.8,lw=1.4)
    ax.axhline(0,color=LIGHT,lw=1.0); ax.set(xlabel="Nominal candidate count, K",ylabel="Median candidate correlation",xticks=[4,8,16,32])
    ax=axs[1,1]; panel(ax,"D","Endpoint and reference sensitivity")
    q=d[(d.candidate_count.eq(32))&(d.transformation.eq("fixed_reference_relative"))].sort_values("ledoit_wolf_entropy_rank"); y=np.arange(len(q))
    for i,(_,r) in enumerate(q.iterrows()):
        lv=loo[(loo.task.eq(r.task))&(loo.transformation.eq("fixed_reference_relative"))&(loo.omission_type.eq("seed"))].entropy_rank
        fv=loo[(loo.task.eq(r.task))&(loo.transformation.eq("fixed_reference_relative"))&(loo.omission_type.eq("outer_fold"))].entropy_rank
        rv=refs[(refs.task.eq(r.task))&refs.reference_label.eq("fixed_morgan_rf")].ledoit_wolf_entropy_rank
        ax.plot([lv.min(),lv.max()],[i,i],color=GREY,lw=1.5,ls="-"); ax.plot([fv.min(),fv.max()],[i+.10,i+.10],color=GREY,lw=1.2,ls="--"); ax.plot(r.ledoit_wolf_entropy_rank,i,"o",color=TEAL,ms=4.8)
        if len(rv):
            ax.scatter([float(rv.median())],[i],facecolors="white",edgecolors=PURPLE,s=30,lw=1.0)
    ax.set(yticks=y,yticklabels=[DISPLAY[x] for x in q.task],xlabel="Reference-relative\nentropy rank")
    ax.tick_params(axis="y",labelsize=8.0)
    sensitivity_handles=[Line2D([0],[0],color=GREY,ls="-",label="Leave-one-seed"),Line2D([0],[0],color=GREY,ls="--",label="Leave-one-fold"),Line2D([0],[0],marker="o",ls="",mfc="white",mec=PURPLE,label="Predefined reference")]
    fig.legend([*legend_handles,nominal],[h.get_label() for h in [*legend_handles,nominal]],loc="upper center",bbox_to_anchor=(.52,.995),ncol=5,frameon=False)
    fig.legend(handles=sensitivity_handles,loc="upper center",bbox_to_anchor=(.52,.945),ncol=3,frameon=False)
    fig.subplots_adjust(left=.12,right=.98,bottom=.10,top=.82); save(fig,"Figure_2_candidate_diversity_after_adjustment")


def _figure3_legacy():
    ranking=pd.read_csv(MINOR/"ranking_metric_main_summary.csv").sort_values("candidate_count")
    null=pd.read_csv(MINOR/"mechanism_permutation_null_summary.csv")
    signal=pd.read_csv(MINOR/"mechanism_signal_recovery_summary.csv")
    cross=pd.read_csv(NEW/"cross_fitted_complete_intervals.csv")
    controls=pd.read_csv(NEW/"candidate_composition_controls.csv")
    fig,axs=plt.subplots(2,2,figsize=(7.2,5.25))
    ax=axs[0,0]; panel(ax,"A","Chance-adjusted top-rank recovery")
    envelope=null.groupby("candidate_count",as_index=False).agg(null_low=("null_q025","min"),null_high=("null_q975","max"))
    ax.fill_between(envelope.candidate_count,envelope.null_low,envelope.null_high,color=GREY,alpha=.12,label="Permutation 95% envelope",zorder=0)
    ax.plot(ranking.candidate_count,ranking.chance_adjusted_hit_median,"o-",color=BLUE,label="CAHit@3",lw=1.6,ms=5)
    ax.fill_between(ranking.candidate_count,ranking.chance_adjusted_hit_q25,ranking.chance_adjusted_hit_q75,color=BLUE,alpha=.07)
    ax.plot(ranking.candidate_count,ranking.normalized_mrr_gain_median,"s-",color=TEAL,label="Normalized MRR gain",lw=1.6,ms=5)
    ax.fill_between(ranking.candidate_count,ranking.normalized_mrr_gain_q25,ranking.normalized_mrr_gain_q75,color=TEAL,alpha=.07)
    ax.axhline(0,color=GREY,lw=1.0); ax.set(xlabel="K",ylabel="Chance-adjusted score",xticks=[4,8,16,32],ylim=(-.38,1.05)); ax.legend(frameon=False,loc="upper right",fontsize=8.5)
    ax=axs[0,1]; panel(ax,"B","Signal-recovery calibration")
    for k,c,m in zip([4,8,16,32],[BLUE,TEAL,ORANGE,PURPLE],["o","s","^","D"]):
        q=signal[signal.candidate_count.eq(k)].sort_values("injected_signal")
        ax.plot(q.injected_signal,q.chance_adjusted_hit_median,marker=m,label=f"K={k}",color=c,lw=1.45,ms=4.6)
    ax.axhline(0,color=LIGHT,lw=.8); ax.set(xlabel="Injected validation–audit signal",ylabel="Median CAHit@3",xticks=[0,.25,.5,.75,1],ylim=(-.08,1.05)); ax.legend(frameon=False,ncol=2,loc="upper left")
    sub=axs[1,0].get_subplotspec().subgridspec(1,2,wspace=.58); left=fig.add_subplot(sub[0,0]); right=fig.add_subplot(sub[0,1]); axs[1,0].remove(); panel(left,"C","Cross-fitted endpoint effects",label_x=-.25)
    for ax,t,c,xlab in [(left,"classification",BLUE,"ROC-AUC loss"),(right,"regression",ORANGE,"RMSE loss")]:
        q=cross[cross.task_type.eq(t)].sort_values("cross_fitted_effect"); y=np.arange(len(q)); x=q.cross_fitted_effect.to_numpy()
        lo=q.split_seed_bootstrap95_low_cross_fitted.to_numpy(); hi=q.split_seed_bootstrap95_high_cross_fitted.to_numpy(); ax.errorbar(x,y,xerr=[x-lo,hi-x],fmt="none",ecolor=GREY,capsize=2.5,lw=1.0)
        for xi,yi,li,hii in zip(x,y,lo,hi):
            marker="o" if xi>=0 else "s"; significant=li>0 or hii<0
            ax.scatter(xi,yi,marker=marker,facecolors=c if significant else "white",edgecolors=c,s=32,lw=1.0)
        ax.axvline(0,color=INK,lw=.8); ax.set(yticks=y,yticklabels=[DISPLAY[v] for v in q.task],xlabel=xlab)
        ax.tick_params(axis="y",labelsize=8.5)
    marker_handles=[Line2D([0],[0],marker="o",ls="",mfc=GREY,mec=GREY,label="Filled: 95% CI excludes zero"),Line2D([0],[0],marker="o",ls="",mfc="white",mec=GREY,label="Open: 95% CI includes zero")]
    fig.legend(handles=marker_handles,loc="lower left",bbox_to_anchor=(.055,.015),frameon=False,ncol=2)
    ax=axs[1,1]; panel(ax,"D","Candidate-composition controls")
    for mode,c,m in zip(sorted(controls["mode"].unique()),[BLUE,TEAL,ORANGE,PURPLE,GREY,RED],["o","s","^","D","P","X"]):
        q=controls[controls["mode"].eq(mode)].sort_values("pool_size"); ax.plot(q.pool_size,q.chance_adjusted_hit_mean,marker=m,ls="-",label=mode.replace("_"," "),color=c,lw=1.4,ms=4.8)
    ax.axhline(0,color=LIGHT,lw=.8); ax.set(xlabel="K",ylabel="Chance-adjusted hit",xticks=[4,8,16,32]); ax.legend(frameon=False)
    ax.text(32,.02,"K = 32: complete registry",ha="right",va="bottom",fontsize=8.0,color=GREY)
    fig.tight_layout(rect=[0,.06,1,1],w_pad=1.5,h_pad=1.6); save(fig,"Figure_3_chance_adjusted_ranking_and_selection_gaps")


def figure3():
    ranking=pd.read_csv(MINOR/"ranking_metric_main_summary.csv").sort_values("candidate_count")
    null=pd.read_csv(MINOR/"mechanism_permutation_null_summary.csv")
    signal=pd.read_csv(MINOR/"mechanism_signal_recovery_summary.csv")
    cross=pd.read_csv(NEW/"cross_fitted_complete_intervals.csv")
    controls=pd.read_csv(NEW/"candidate_composition_controls.csv")
    fig=plt.figure(figsize=(7.2,5.65))
    gs=fig.add_gridspec(2,2,left=.105,right=.98,bottom=.065,top=.985,hspace=.28,wspace=.42)

    def structured_cell(spec,label,title):
        sub=spec.subgridspec(3,1,height_ratios=[.10,.13,.77],hspace=0)
        head=fig.add_subplot(sub[0]); head.axis("off")
        head.text(-.13,.18,label,transform=head.transAxes,fontsize=12.0,fontweight="bold",va="bottom",clip_on=False)
        head.text(0,.18,title,transform=head.transAxes,fontsize=10.3,fontweight="bold",va="bottom",clip_on=False)
        leg=fig.add_subplot(sub[1]); leg.axis("off")
        return sub[2],leg

    acontent,aleg=structured_cell(gs[0,0],"A","Chance-adjusted top-rank recovery")
    bcontent,bleg=structured_cell(gs[0,1],"B","Signal-recovery calibration")
    ccontent,cleg=structured_cell(gs[1,0],"C","Cross-fitted endpoint effects")
    dcontent,dleg=structured_cell(gs[1,1],"D","Candidate-composition controls")

    ax=fig.add_subplot(acontent)
    envelope=null.groupby("candidate_count",as_index=False).agg(null_low=("null_q025","min"),null_high=("null_q975","max"))
    ax.fill_between(envelope.candidate_count,envelope.null_low,envelope.null_high,color=GREY,alpha=.12,zorder=0)
    ax.plot(ranking.candidate_count,ranking.chance_adjusted_hit_median,"o-",color=BLUE,lw=1.6,ms=5)
    ax.fill_between(ranking.candidate_count,ranking.chance_adjusted_hit_q25,ranking.chance_adjusted_hit_q75,color=BLUE,alpha=.07)
    ax.plot(ranking.candidate_count,ranking.normalized_mrr_gain_median,"s-",color=TEAL,lw=1.6,ms=5)
    ax.fill_between(ranking.candidate_count,ranking.normalized_mrr_gain_q25,ranking.normalized_mrr_gain_q75,color=TEAL,alpha=.07)
    ax.axhline(0,color=GREY,lw=1.0); ax.set(xlabel="K",ylabel="Chance-adjusted score",xticks=[4,8,16,32],ylim=(-.38,1.05))
    a_handles=[Rectangle((0,0),1,1,fc=GREY,ec=GREY,alpha=.12,label="Permutation 95% envelope"),Line2D([0],[0],marker="o",color=BLUE,label="CAHit@3"),Line2D([0],[0],marker="s",color=TEAL,label="Normalized MRR gain")]
    aleg.legend(handles=a_handles,loc="center",ncol=3,frameon=False,handletextpad=.45,columnspacing=.85,borderpad=0,fontsize=7.6)

    ax=fig.add_subplot(bcontent); b_handles=[]
    for k,color,marker in zip([4,8,16,32],[BLUE,TEAL,ORANGE,PURPLE],["o","s","^","D"]):
        q=signal[signal.candidate_count.eq(k)].sort_values("injected_signal")
        ax.plot(q.injected_signal,q.chance_adjusted_hit_median,marker=marker,color=color,lw=1.45,ms=4.6)
        b_handles.append(Line2D([0],[0],marker=marker,color=color,label=f"K={k}"))
    ax.axhline(0,color=LIGHT,lw=.8); ax.set(xlabel="Injected validation–audit signal",ylabel="Median CAHit@3",xticks=[0,.25,.5,.75,1],ylim=(-.08,1.05))
    bleg.legend(handles=b_handles,loc="center",ncol=4,frameon=False,handletextpad=.45,columnspacing=1.0,borderpad=0)

    csub=ccontent.subgridspec(1,2,wspace=.58); left=fig.add_subplot(csub[0,0]); right=fig.add_subplot(csub[0,1])
    for ax,task_type,color,xlabel in [(left,"classification",BLUE,"ROC-AUC loss"),(right,"regression",ORANGE,"RMSE loss")]:
        q=cross[cross.task_type.eq(task_type)].sort_values("cross_fitted_effect"); y=np.arange(len(q)); xvals=q.cross_fitted_effect.to_numpy()
        lo=q.split_seed_bootstrap95_low_cross_fitted.to_numpy(); hi=q.split_seed_bootstrap95_high_cross_fitted.to_numpy()
        ax.errorbar(xvals,y,xerr=[xvals-lo,hi-xvals],fmt="none",ecolor=GREY,capsize=2.5,lw=1.0)
        for xi,yi,li,hii in zip(xvals,y,lo,hi):
            marker="o" if xi>=0 else "s"; significant=li>0 or hii<0
            ax.scatter(xi,yi,marker=marker,facecolors=color if significant else "white",edgecolors=color,s=32,lw=1.0)
        ax.axvline(0,color=INK,lw=.8); ax.set(yticks=y,yticklabels=[DISPLAY[v] for v in q.task],xlabel=xlabel)
        ax.tick_params(axis="y",labelsize=8.5)
    marker_handles=[Line2D([0],[0],marker="o",ls="",mfc=GREY,mec=GREY,label="Filled: 95% CI excludes zero"),Line2D([0],[0],marker="o",ls="",mfc="white",mec=GREY,label="Open: 95% CI includes zero")]
    cleg.legend(handles=marker_handles,loc="center",frameon=False,ncol=2,handletextpad=.5,columnspacing=1.1,borderpad=0,fontsize=7.7)

    ax=fig.add_subplot(dcontent); d_handles=[]
    for mode,color,marker in zip(sorted(controls["mode"].unique()),[BLUE,TEAL,ORANGE,PURPLE,GREY,RED],["o","s","^","D","P","X"]):
        q=controls[controls["mode"].eq(mode)].sort_values("pool_size")
        ax.plot(q.pool_size,q.chance_adjusted_hit_mean,marker=marker,ls="-",color=color,lw=1.4,ms=4.8)
        d_handles.append(Line2D([0],[0],marker=marker,color=color,label=mode.replace("_"," ")))
    ax.axhline(0,color=LIGHT,lw=.8); ax.set(xlabel="K",ylabel="Chance-adjusted hit",xticks=[4,8,16,32])
    ax.text(32,.02,"K = 32: complete registry",ha="right",va="bottom",fontsize=8.0,color=GREY)
    dleg.legend(handles=d_handles,loc="center",ncol=2,frameon=False,handletextpad=.45,columnspacing=1.0,borderpad=0,fontsize=7.7)
    save(fig,"Figure_3_chance_adjusted_ranking_and_selection_gaps")


def figure4():
    units=pd.read_csv(CORE/"audit_gap_decomposition_units.csv")
    cross=pd.read_csv(NEW/"cross_fitted_complete_intervals.csv")
    fold=pd.read_csv(NEW/"cross_fitted_fold_effects.csv")
    sim=pd.read_csv(PREV/"paper19_oracle_extreme_value_simulation.csv")
    q=units[units.candidate_count.eq(32)].groupby(["task","task_type"],as_index=False).agg(audit=("observed_audit_best_gain","mean"),selected=("selected_model_gain","mean"))
    fig=plt.figure(figsize=(7.2,6.10)); gs=fig.add_gridspec(2,2,left=.105,right=.98,bottom=.065,top=.985,hspace=.24,wspace=.42)

    def structured_cell(spec,label,title,handles=None,ncol=2,label_x=-.13,title_x=0.0):
        sub=spec.subgridspec(3,1,height_ratios=[.10,.095,.805],hspace=0)
        head=fig.add_subplot(sub[0]); head.axis("off")
        head.text(label_x,.18,label,transform=head.transAxes,fontsize=12.0,fontweight="bold",va="bottom",clip_on=False)
        head.text(title_x,.18,title,transform=head.transAxes,fontsize=10.3,fontweight="bold",va="bottom",clip_on=False)
        leg=fig.add_subplot(sub[1]); leg.axis("off")
        if handles:
            leg.legend(handles=handles,loc="center",ncol=ncol,frameon=False,handletextpad=.45,columnspacing=1.1,borderpad=0)
        return sub[2]

    selected_handle=Line2D([0],[0],marker="o",ls="",color=TEAL,label="Validation-selected gain")
    a_handles=[selected_handle,Line2D([0],[0],marker="o",ls="",color=BLUE,label="Observed audit-best gain")]
    b_handles=[selected_handle,Line2D([0],[0],marker="o",ls="",color=ORANGE,label="Observed audit-best gain")]
    top_specs=[
        structured_cell(gs[0,0],"A","Classification opportunity and realization",a_handles,label_x=-.13),
        structured_cell(gs[0,1],"B","Regression opportunity and realization",b_handles,label_x=-.13),
    ]
    top_axes=[fig.add_subplot(top_specs[0]),fig.add_subplot(top_specs[1])]
    for ax,t,c,label in [(top_axes[0],"classification",BLUE,"ROC-AUC gain"),(top_axes[1],"regression",ORANGE,"RMSE reduction")]:
        z=q[q.task_type.eq(t)].sort_values("audit"); y=np.arange(len(z))
        for yi,s,a in zip(y,z.selected,z.audit): ax.plot([s,a],[yi,yi],color=LIGHT,lw=1.6,zorder=1)
        ax.scatter(z.selected,y,color=TEAL,label="Validation-selected gain",s=36,zorder=3); ax.scatter(z.audit,y,color=c,label="Observed audit-best gain",s=36,zorder=3)
        ax.axvline(0,color=GREY,lw=.9); ax.set(yticks=y,yticklabels=[DISPLAY[v] for v in z.task],xlabel=label); ax.tick_params(axis="y",labelsize=8.0)

    gap_handles=[Line2D([0],[0],marker="o",ls="",mfc="#71879C",mec=BLUE,label="Same-unit"),Line2D([0],[0],marker="s",ls="",mfc=TEAL,mec=BLUE,label="Cross-fitted"),Line2D([0],[0],marker="o",ls="",mfc="white",mec=GREY,label="Open: CI crosses zero")]
    ccontent=structured_cell(gs[1,0],"C","Same-unit and cross-fitted effects",gap_handles,ncol=3,label_x=-.13,title_x=0.0)
    dcontent=structured_cell(gs[1,1],"D","Finite-audit winner optimism",None,label_x=-.13,title_x=0.0)
    # Reserve a true caption row beneath the tick labels.  The label spans the
    # complete panel (forest plot plus numerical summary), so it stays centred
    # on panel C rather than on the plotting axis alone.
    crows=ccontent.subgridspec(2,1,height_ratios=[.82,.18],hspace=.06)
    csub=crows[0].subgridspec(1,2,width_ratios=[.54,.46],wspace=.04); cax=fig.add_subplot(csub[0,0]); ctext=fig.add_subplot(csub[0,1],sharey=cax); ctext.axis("off")
    scale=(fold.groupby("task").apply(lambda g: max(float(np.quantile(np.r_[g.same_unit_effect.abs(),g.cross_fitted_effect.abs()],.95)),1e-12),include_groups=False).rename("visualization_scale"))
    src=cross.merge(scale,on="task",how="left")
    src["unit"]=np.where(src.task_type.eq("classification"),"ROC-AUC","RMSE")
    for method in ["same_unit","cross_fitted"]:
        src[f"normalized_{method}_effect"]=src[f"{method}_effect"]/src.visualization_scale
        src[f"normalized_{method}_ci_low"]=src[f"split_seed_bootstrap95_low_{method}"]/src.visualization_scale
        src[f"normalized_{method}_ci_high"]=src[f"split_seed_bootstrap95_high_{method}"]/src.visualization_scale
        src[f"{method}_ci_excludes_zero"]=(src[f"split_seed_bootstrap95_low_{method}"]>0)|(src[f"split_seed_bootstrap95_high_{method}"]<0)
    src["scale_definition"]="95th percentile of absolute fold-level same-unit and cross-fitted K=32 minus K=4 effects within endpoint"
    class_order=src[src.task_type.eq("classification")].sort_values("cross_fitted_effect",ascending=False)
    reg_order=src[src.task_type.eq("regression")].sort_values("cross_fitted_effect",ascending=False)
    src=pd.concat([class_order,reg_order],ignore_index=True); src["display_order"]=np.arange(1,len(src)+1)
    SOURCE.mkdir(parents=True,exist_ok=True); src.to_csv(SOURCE/"Figure_4C_integrated_forest_source.csv",index=False,encoding="utf-8-sig")
    y=np.arange(len(src)); same_color="#71879C"
    for yi,r in zip(y,src.itertuples()):
        task_color=BLUE if r.task_type=="classification" else ORANGE
        cax.plot([r.normalized_same_unit_effect,r.normalized_cross_fitted_effect],[yi,yi],color=LIGHT,lw=1.4,zorder=1)
        for method,marker,fill_color,offset in [("same_unit","o",same_color,-.075),("cross_fitted","s",TEAL,.075)]:
            x=getattr(r,f"normalized_{method}_effect"); lo=getattr(r,f"normalized_{method}_ci_low"); hi=getattr(r,f"normalized_{method}_ci_high")
            significant=getattr(r,f"{method}_ci_excludes_zero")
            cax.errorbar(x,yi+offset,xerr=[[x-lo],[hi-x]],fmt="none",ecolor=fill_color,lw=.9,capsize=2.2,zorder=2)
            cax.scatter(x,yi+offset,marker=marker,s=34,facecolors=fill_color if significant else "white",edgecolors=task_color,lw=1.0,zorder=3)
        unit_short="AUC" if r.task_type=="classification" else "RMSE"
        ctext.text(.02,yi,f"{r.same_unit_effect:+.3f}",ha="left",va="center",fontsize=8.0,color=INK)
        ctext.text(.38,yi,f"{r.cross_fitted_effect:+.3f}",ha="left",va="center",fontsize=8.0,color=INK)
        ctext.text(.78,yi,unit_short,ha="left",va="center",fontsize=8.0,color=task_color)
    sep=len(class_order)-.5; cax.axhline(sep,color=LIGHT,lw=1.0); ctext.axhline(sep,color=LIGHT,lw=1.0)
    cax.axvline(0,color=INK,lw=.9); cax.set(yticks=y,yticklabels=[DISPLAY[t] for t in src.task]); cax.invert_yaxis(); cax.set_ylim(len(src)-.5,-1.0); ctext.set_ylim(cax.get_ylim())
    cax.tick_params(axis="y",labelsize=8.0); ctext.text(.02,-.65,"Same",transform=ctext.get_yaxis_transform(),ha="left",va="center",fontsize=8.0,fontweight="bold"); ctext.text(.38,-.65,"Cross",transform=ctext.get_yaxis_transform(),ha="left",va="center",fontsize=8.0,fontweight="bold"); ctext.text(.78,-.65,"Metric",transform=ctext.get_yaxis_transform(),ha="left",va="center",fontsize=8.0,fontweight="bold")
    clabel=fig.add_subplot(crows[1]); clabel.axis("off"); clabel.text(.5,.08,"Within-endpoint normalized K = 32 minus K = 4 effect",ha="center",va="bottom",fontsize=9.2)

    drows=dcontent.subgridspec(2,1,height_ratios=[.82,.18],hspace=.06)
    ax=fig.add_subplot(drows[0])
    z=sim[(sim.truth_scenario.eq("equal_truth"))&(sim.pairwise_candidate_correlation.eq(.9))]; grid=z.pivot_table(index="effective_audit_sample_size",columns="candidate_count",values="mean_observed_oracle_optimism").sort_index(ascending=False)
    im=ax.imshow(grid,aspect="auto",cmap="cividis"); ax.set(xticks=np.arange(len(grid.columns)),xticklabels=grid.columns,yticks=np.arange(len(grid.index)),yticklabels=grid.index,ylabel="Effective audit size")
    threshold=float((np.nanmin(grid.to_numpy())+np.nanmax(grid.to_numpy()))/2)
    for iy in range(grid.shape[0]):
        for ix in range(grid.shape[1]):
            value=float(grid.iloc[iy,ix]); ax.text(ix,iy,f"{value:.2f}",ha="center",va="center",fontsize=8.0,color="white" if value<threshold else INK)
    cb=fig.colorbar(im,ax=ax,fraction=.085,pad=.04,label="Mean winner optimism"); cb.ax.tick_params(labelsize=8.5); cb.ax.yaxis.label.set_size(9.0)
    dlabel=fig.add_subplot(drows[1]); dlabel.axis("off"); dlabel.text(.5,.08,"K",ha="center",va="bottom",fontsize=9.2)
    save(fig,"Figure_4_selection_gap_and_winner_optimism")


def figure5():
    units=pd.read_csv(NEW/"matched_k3_220_subset_units.csv"); summ=pd.read_csv(NEW/"matched_k3_220_subset_summary.csv")
    ladder=pd.read_csv(CORE/"matched_k_multiview_summary.csv")
    class_tasks=sorted(summ.loc[summ.task_type.eq("classification"),"task"].unique()); reg_tasks=sorted(summ.loc[summ.task_type.eq("regression"),"task"].unique()); task_order=[*class_tasks,*reg_tasks]
    task_scales={}
    for task in task_order:
        values=summ.loc[summ.task.eq(task),"selected_model_gain_median"].to_numpy(float); task_scales[task]=max(float(np.median(np.abs(values-np.median(values)))),1e-12)
    fig=plt.figure(figsize=(7.2,6.15)); gs=four_panel_grid(fig,bottom=.17,top=.94,hspace=.50,wspace=.43)
    ax=fig.add_subplot(gs[0,0]); panel(ax,"A","Endpoint-specific K = 3 subset distributions")
    rng=np.random.default_rng(20260713)
    for i,task in enumerate(task_order):
        x=summ.loc[summ.task.eq(task),"selected_model_gain_median"].to_numpy(float)/task_scales[task]
        jitter=rng.uniform(-.11,.11,len(x)); color=BLUE if task in class_tasks else ORANGE
        violin=ax.violinplot([x],positions=[i],vert=False,widths=.55,showextrema=False)
        for body in violin["bodies"]:
            vertices=body.get_paths()[0].vertices; vertices[:,1]=np.minimum(vertices[:,1],i)
            body.set(facecolor=color,edgecolor="none",alpha=.10,zorder=.5)
        ax.scatter(x,np.full(len(x),i)+jitter,s=7,color=color,alpha=.18,rasterized=True,zorder=1)
        bp=ax.boxplot([x],positions=[i],vert=False,widths=.36,showfliers=False,patch_artist=True,manage_ticks=False,zorder=2)
        for box in bp["boxes"]: box.set(facecolor="white",edgecolor=GREY,linewidth=.9)
        for key in ["whiskers","caps","medians"]:
            for artist in bp[key]: artist.set(color=INK if key=="medians" else GREY,linewidth=1.0)
    ax.axvline(0,color=INK,lw=.9); ax.axhline(len(class_tasks)-.5,color=LIGHT,lw=1.0); ax.set_xscale("symlog",linthresh=2,linscale=1)
    ax.set(yticks=np.arange(len(task_order)),yticklabels=[DISPLAY[t] for t in task_order],xlabel="Selected-model gain / endpoint MAD (symmetric-log display)"); ax.invert_yaxis(); ax.tick_params(axis="y",labelsize=8.0)
    ax.set_xticks([-10,-1,0,1,10])
    ax.set_xticklabels(["-10","-1","0","1","10"])
    ax=fig.add_subplot(gs[0,1]); panel(ax,"B","Endpoint-by-composition median gain")
    cats=["single-representation only","single-learner only","representation-balanced without concatenation","representation-balanced with concatenation","mixed unbalanced"]
    rows=[]
    for task in task_order:
        row=[summ[(summ.task.eq(task))&summ.composition_class.eq(c)].selected_model_gain_median.median() for c in cats]
        rows.append(row)
    a=np.asarray(rows); norm=a/np.asarray([task_scales[t] for t in task_order])[:,None]; lim=max(float(np.nanquantile(np.abs(norm),.95)),1e-12); clipped=np.abs(norm)>lim
    short_cats=["Single repr.","Single learner","Balanced – concat.","Balanced + concat.","Mixed"]
    short_cats=["Single repr.","Single learner","Balanced - concat.","Balanced + concat.","Mixed"]
    im=ax.imshow(np.clip(norm,-lim,lim),aspect="auto",cmap="RdBu_r",vmin=-lim,vmax=lim); ax.set(yticks=np.arange(len(rows)),xticks=np.arange(len(cats)),xticklabels=short_cats,yticklabels=[]); ax.set_ylabel("Endpoints (order as A)"); plt.setp(ax.get_xticklabels(),rotation=20,ha="right"); cb=fig.colorbar(im,ax=ax,fraction=.055,pad=.03,label="Median gain / endpoint MAD"); cb.ax.tick_params(labelsize=7.5); ax.tick_params(axis="y",labelsize=8.0)
    for yi,xi in np.argwhere(clipped): ax.scatter(xi,yi,marker="^" if norm[yi,xi]>0 else "v",s=12,facecolors="none",edgecolors=INK,lw=.7)
    ax=fig.add_subplot(gs[1,0]); panel(ax,"C","Incremental K ladder",label_x=-.16,title_x=.06)
    z=ladder[ladder.analysis_group.eq("incremental_ladder")].copy(); z["pool_size"]=z.pool_size.astype(int)
    z["normalized_gain"]=z.groupby("task").mean_gain_vs_morgan_k3.transform(lambda x:x/max(x.abs().max(),1e-12))
    for task in sorted(z.task.unique()):
        q=z[z.task.eq(task)].sort_values("pool_size"); task_type=q.task_type.iloc[0]; ax.plot(q.pool_size,q.normalized_gain,color=BLUE if task_type=="classification" else ORANGE,ls="-" if task_type=="classification" else "--",alpha=.14,lw=.9)
    for task_type,c,ls in [("classification",BLUE,"-"),("regression",ORANGE,"--")]:
        g=z[z.task_type.eq(task_type)].groupby("pool_size").normalized_gain; med=g.median(); lo=g.quantile(.25); hi=g.quantile(.75); ax.plot(med.index,med.values,"o",ls=ls,color=c,lw=1.8,label=f"{task_type.title()} median"); ax.fill_between(med.index,lo.values,hi.values,color=c,alpha=.07)
    ax.axhline(0,color=INK,lw=.8); ax.set(ylabel="Endpoint-scaled gain",xticks=[3,6,9,12]); ax.text(.02,.04,"max |gain| = 1",transform=ax.transAxes,ha="left",va="bottom",fontsize=8.0,color=GREY,bbox=dict(fc="white",ec="none",alpha=.82,pad=.8))
    ladder_handles=[Line2D([0],[0],marker="o",color=BLUE,ls="-",label="Classification median"),Line2D([0],[0],marker="o",color=ORANGE,ls="--",label="Regression median")]
    fig.legend(handles=ladder_handles,loc="lower left",bbox_to_anchor=(.09,.105),ncol=2,frameon=False)

    dsub=gs[1,1].subgridspec(1,2,width_ratios=[.61,.39],wspace=.04); dax=fig.add_subplot(dsub[0,0]); dtext=fig.add_subplot(dsub[0,1],sharey=dax); dtext.axis("off"); panel(dax,"D","Endpoint-specific representation effects",label_x=-.18,title_x=.08)
    qraw=(summ.groupby(["task","task_type"])["selected_model_gain_median"]
          .agg(median="median",lo=lambda x:x.quantile(.025),hi=lambda x:x.quantile(.975)).reset_index())
    qraw["endpoint_mad"]=qraw.task.map(task_scales); qraw["normalized_median"]=qraw["median"]/qraw.endpoint_mad; qraw["normalized_lo"]=qraw.lo/qraw.endpoint_mad; qraw["normalized_hi"]=qraw.hi/qraw.endpoint_mad; qraw["unit"]=np.where(qraw.task_type.eq("classification"),"ROC-AUC gain","RMSE reduction")
    qraw["interval_type"]="2.5th to 97.5th percentile distribution range across 220 registered K=3 subsets; not a confidence interval"
    qraw=pd.concat([qraw[qraw.task_type.eq("classification")].sort_values("normalized_median",ascending=False),qraw[qraw.task_type.eq("regression")].sort_values("normalized_median",ascending=False)],ignore_index=True); qraw["display_order"]=np.arange(1,len(qraw)+1)
    qraw.to_csv(SOURCE/"Figure_5D_integrated_forest_source.csv",index=False,encoding="utf-8-sig")
    limit=max(10.0,float(np.quantile(np.abs(qraw.normalized_median),.85))); y=np.arange(len(qraw))
    for yi,r in zip(y,qraw.itertuples()):
        color=BLUE if r.task_type=="classification" else ORANGE; lo=max(r.normalized_lo,-limit); hi=min(r.normalized_hi,limit); med=np.clip(r.normalized_median,-limit,limit)
        dax.plot([lo,hi],[yi,yi],color=GREY,lw=1.3); dax.plot([lo,lo],[yi-.08,yi+.08],color=GREY,lw=1.0); dax.plot([hi,hi],[yi-.08,yi+.08],color=GREY,lw=1.0)
        marker="o" if abs(r.normalized_median)<=limit else (">" if r.normalized_median>0 else "<"); dax.scatter(med,yi,color=color,marker=marker,s=34,zorder=3)
        if r.normalized_lo < -limit: dax.scatter(-limit,yi,marker="<",facecolors="white",edgecolors=color,s=30,lw=1.0)
        if r.normalized_hi > limit: dax.scatter(limit,yi,marker=">",facecolors="white",edgecolors=color,s=30,lw=1.0)
        unit_short="AUC" if r.task_type=="classification" else "RMSE"
        dtext.text(.02,yi,f"{r.median:+.4f}  {unit_short}",ha="left",va="center",fontsize=8.0,color=color)
    sep=len(class_tasks)-.5; dax.axhline(sep,color=LIGHT,lw=1.0); dtext.axhline(sep,color=LIGHT,lw=1.0); dax.axvline(0,color=INK,lw=.9)
    dax.set(yticks=y,yticklabels=[DISPLAY[t] for t in qraw.task],xlim=(-limit*1.08,limit*1.08)); dax.invert_yaxis(); dax.set_ylim(len(qraw)-.5,-1.0); dtext.set_ylim(dax.get_ylim()); dax.tick_params(axis="y",labelsize=8.0)
    dtext.text(.02,-.65,"Raw effect (unit)",transform=dtext.get_yaxis_transform(),ha="left",va="center",fontsize=8.0,fontweight="bold")
    dcell=gs[1,1].get_position(fig)
    fig.text((dcell.x0+dcell.x1)/2,dcell.y0-.045,"Selected-model gain / endpoint MAD",ha="center",va="center",fontsize=9.2)
    save(fig,"Figure_5_matched_size_multiview_composition")


def figure6():
    support=pd.read_csv(NEW/"chemical_support_selection_audit.csv")
    scaff=pd.read_csv(NEW/"scaffold_novelty_error_complementarity.csv")
    perf=pd.read_csv(HARD/"six_task_strong_endpoint_table.csv")
    diversity=pd.read_csv(NEW/"prediction_level_effective_diversity.csv")
    fig=plt.figure(figsize=(7.2,6.25)); gs=fig.add_gridspec(2,2,left=.10,right=.98,bottom=.12,top=.94,hspace=.62,wspace=.58,width_ratios=[1.08,.92])

    ax=fig.add_subplot(gs[0,0]); panel(ax,"A","Prediction and error similarity",label_x=-.16)
    raw=pd.read_csv(HARD/"six_task_strong_baseline_outer_predictions.csv")
    candidates=["rdkit_rf","gnn_gcn","chemberta_mtr_linear_probe","molformer_linear_probe"]
    raw=raw[raw.candidate.isin(candidates)].copy(); corrs=[]; jacc=[]
    for _,g in raw.groupby(["task","seed","outer_fold"]):
        wide=g.pivot(index="sample_index",columns="candidate",values="y_pred").reindex(columns=candidates); corrs.append(wide.corr().to_numpy())
        err=g.assign(abs_error=(g.y_true-g.y_pred).abs()); err["high"]=err.groupby("candidate").abs_error.transform(lambda x:x>=x.quantile(.75)); flags=err.pivot(index="sample_index",columns="candidate",values="high").reindex(columns=candidates).to_numpy(bool); mat=np.eye(len(candidates))
        for i in range(len(candidates)):
            for j in range(len(candidates)):
                union=(flags[:,i]|flags[:,j]).sum(); mat[i,j]=(flags[:,i]&flags[:,j]).sum()/union if union else np.nan
        jacc.append(mat)
    corr=np.nanmedian(corrs,axis=0); jac=np.nanmedian(jacc,axis=0)
    lower=np.ma.masked_where(~np.tril(np.ones_like(corr,dtype=bool),-1),corr)
    upper=np.ma.masked_where(~np.triu(np.ones_like(jac,dtype=bool),1),jac)
    ax.imshow(lower,vmin=0,vmax=1,cmap="Blues",aspect="auto",interpolation="nearest")
    ax.imshow(upper,vmin=0,vmax=1,cmap="Purples",aspect="auto",interpolation="nearest")
    for i in range(len(candidates)): ax.add_patch(Rectangle((i-.5,i-.5),1,1,fc="#F1F3F4",ec="white",lw=.9))
    for i in range(len(candidates)):
        for j in range(len(candidates)):
            if i>j:
                value=corr[i,j]; color="white" if value>.55 else INK
            elif i<j:
                value=jac[i,j]; color="white" if value>.55 else INK
            else:
                continue
            ax.text(j,i,f"{value:.2f}",ha="center",va="center",fontsize=7.6,color=color)
    short_x=["RF","GCN","Chem-\nBERTa","MoL-\nFormer"]; short_y=["RF","GCN","Chem-\nBERTa","MoL-\nFormer"]
    ax.set(xticks=np.arange(4),xticklabels=short_x,yticks=np.arange(4),yticklabels=short_y)
    ax.tick_params(axis="both",length=0,pad=2,labelsize=7.6); ax.set_xlim(-.5,3.5); ax.set_ylim(3.5,-.5)
    for spine in ax.spines.values(): spine.set_visible(False)
    pred_cax=inset_axes(ax,width="42%",height="4.5%",loc="lower left",bbox_to_anchor=(0,-.25,1,1),bbox_transform=ax.transAxes,borderpad=0)
    err_cax=inset_axes(ax,width="42%",height="4.5%",loc="lower right",bbox_to_anchor=(0,-.25,1,1),bbox_transform=ax.transAxes,borderpad=0)
    pred_cb=fig.colorbar(mpl.cm.ScalarMappable(norm=mpl.colors.Normalize(0,1),cmap="Blues"),cax=pred_cax,orientation="horizontal")
    err_cb=fig.colorbar(mpl.cm.ScalarMappable(norm=mpl.colors.Normalize(0,1),cmap="Purples"),cax=err_cax,orientation="horizontal")
    pred_cb.ax.set_title("Prediction r",fontsize=8.0,fontweight="bold",pad=2); err_cb.ax.set_title("Error Jaccard",fontsize=8.0,fontweight="bold",pad=2)
    pred_cb.ax.tick_params(labelsize=8.0,pad=1); err_cb.ax.tick_params(labelsize=8.0,pad=1)

    SOURCE.mkdir(parents=True,exist_ok=True); matrix_rows=[]
    for i,mi in enumerate(candidates):
        for j,mj in enumerate(candidates):
            if i>j: matrix_rows.append({"row_model":mi,"column_model":mj,"triangle":"lower","metric":"prediction_correlation","value":corr[i,j]})
            elif i<j: matrix_rows.append({"row_model":mi,"column_model":mj,"triangle":"upper","metric":"high_error_jaccard","value":jac[i,j]})
    pd.DataFrame(matrix_rows).to_csv(SOURCE/"Figure_6A_double_triangle_matrix_source.csv",index=False,encoding="utf-8-sig")
    summary=pd.DataFrame([{
        "nominal_models":4,
        "prediction_lw_entropy_rank":diversity.prediction_lw_entropy_rank.mean(),
        "prediction_participation_rank":diversity.prediction_participation_rank.mean(),
        "error_lw_entropy_rank":diversity.error_lw_entropy_rank.mean(),
        "error_participation_rank":diversity.error_participation_rank.mean(),
        "utility_vs_prediction_variance_rank_spearman":diversity.utility_vs_prediction_variance_rank_spearman.mean(),
        "aggregation":"mean across endpoint-seed-outer-fold units",
    }])
    summary.to_csv(SOURCE/"Figure_6A_prediction_diversity_summary.csv",index=False,encoding="utf-8-sig")
    bax=fig.add_subplot(gs[0,1]); panel(bax,"B","Chemical-support performance and risk",label_x=-.13)
    order=["<0.5","0.5-0.7",">0.7"]; support_labels=["Low","Intermediate","High"]
    support_risk_rows=[
        ("classification","selected_performance","ROC-AUC","higher_is_better"),
        ("regression","selected_performance","RMSE","higher_is_worse"),
        ("classification","false_negative_rate","FNR","higher_is_worse"),
        ("classification","high_error_enrichment","HE enrichment (class.)","higher_is_worse"),
        ("regression","high_error_enrichment","HE enrichment (regr.)","higher_is_worse"),
    ]
    support_matrix=[]; support_source=[]
    for task_type,metric,label,direction in support_risk_rows:
        z=support[support.task_type.eq(task_type)].groupby(["seed","tanimoto_bin"],as_index=False)[metric].median(); values=[]
        for support_bin in order:
            sv=z.loc[z.tanimoto_bin.eq(support_bin),metric].dropna().to_numpy(float); med=float(np.median(sv)); q25=float(np.quantile(sv,.25)); q75=float(np.quantile(sv,.75)); values.append(med); support_source.append({"task_type":task_type,"metric":metric,"display_label":label,"direction":direction,"tanimoto_bin":support_bin,"n_seed_summaries":len(sv),"median":med,"q25":q25,"q75":q75})
        values=np.asarray(values,float); span=max(float(values.max()-values.min()),1e-12); adverse=(values.max()-values)/span if direction=="higher_is_better" else (values-values.min())/span; support_matrix.append(adverse)
    support_matrix=np.asarray(support_matrix); pd.DataFrame(support_source).to_csv(SOURCE/"Figure_6B_support_risk_matrix_source.csv",index=False,encoding="utf-8-sig")
    bax.imshow(support_matrix,aspect="auto",cmap="RdYlGn_r",vmin=0,vmax=1,interpolation="nearest")
    for yi,(_,_,_,_) in enumerate(support_risk_rows):
        row_values=[r["median"] for r in support_source if r["display_label"]==support_risk_rows[yi][2]]
        for xi,value in enumerate(row_values): bax.text(xi,yi,f"{value:.3f}",ha="center",va="center",fontsize=7.5,color=INK,fontweight="semibold")
    bax.set(xticks=np.arange(3),xticklabels=support_labels,yticks=np.arange(len(support_risk_rows)),yticklabels=[x[2] for x in support_risk_rows],xlabel="Chemical support (Tanimoto strata)")
    bax.tick_params(axis="both",length=0,labelsize=8.0); bax.text(.99,-.16,"Cell text: natural-scale median; colour: within-row adverse direction",transform=bax.transAxes,ha="right",va="top",fontsize=8.0,color=GREY)
    for spine in bax.spines.values(): spine.set_visible(False)

    ax=fig.add_subplot(gs[1,0]); panel(ax,"C","Novel-scaffold reliability shifts",label_x=-.12,title_x=.05)
    keys=["task","task_type","seed","outer_fold"]
    metrics=[
        ("high_error_enrichment","High-error enrichment",PURPLE,None),
        ("false_negative_enrichment","False-negative enrichment",RED,"classification"),
        ("mean_model_disagreement","Model disagreement",TEAL,None),
        ("mean_pairwise_high_error_jaccard","Error overlap",BLUE,None),
    ]
    ratio_rows=[]
    for col,label,color,task_filter in metrics:
        subset=scaff if task_filter is None else scaff[scaff.task_type.eq(task_filter)]
        wide=subset.pivot_table(index=keys,columns="scaffold_relation",values=col).dropna(); value=wide.novel_scaffold/wide.seen_or_related_scaffold.replace(0,np.nan); value=value.replace([np.inf,-np.inf],np.nan).dropna()
        ratio_rows.append({"metric":col,"label":label,"task_filter":task_filter or "all","n_units":len(value),"median_ratio":np.nanmedian(value),"q025":np.nanquantile(value,.025),"q975":np.nanquantile(value,.975),"color":color})
    ratio_frame=pd.DataFrame(ratio_rows); ratio_frame.drop(columns="color").to_csv(SOURCE/"Figure_6C_scaffold_reliability_source.csv",index=False,encoding="utf-8-sig")
    yy=np.arange(len(ratio_frame))
    for yi,r in enumerate(ratio_frame.itertuples()):
        ax.errorbar(r.median_ratio,yi,xerr=[[r.median_ratio-r.q025],[r.q975-r.median_ratio]],fmt="none",ecolor=GREY,capsize=2,lw=1.1); ax.scatter(r.median_ratio,yi,color=r.color,s=24,zorder=3)
        text_x=min(r.median_ratio*1.08,5.6); ax.text(text_x,yi,f"{r.median_ratio:.2f}",ha="left",va="center",fontsize=7.5,color=r.color)
    ax.axvline(1,color=INK,lw=.8); ax.set_xscale("log",base=2); ax.set(yticks=yy,yticklabels=ratio_frame.label,xlabel="Novel / seen-or-related scaffold ratio",xlim=(.5,6)); ax.set_xticks([.5,1,2,4]); ax.set_xticklabels(["0.5","1","2","4"]); ax.invert_yaxis(); ax.grid(axis="x",color=LIGHT,lw=.7)

    dax=fig.add_subplot(gs[1,1]); panel(dax,"D","ClinTox four-model trade-offs",label_x=-.10,title_x=.04)
    neg=pd.read_csv(ROOT/"output"/"sci1_mechanism_uq_decision_20260707"/"clintox_minority_negative_result.csv")
    clintox_perf=perf[(perf.task.eq("clintox"))&perf.candidate.isin(candidates)][["candidate","mean_roc_auc","mean_pr_auc"]]
    clintox_rel=neg[(neg.method.eq("label_conditional_conformal"))&neg.candidate.isin(candidates)][["candidate","minority_recall","minority_false_negative_rate","mean_class_1_coverage","mean_set_size"]]
    dsource=clintox_perf.merge(clintox_rel,on="candidate",how="inner"); dsource["mean_set_size_mapped_1_to_2"] = dsource.mean_set_size-1.0; dsource.to_csv(SOURCE/"Figure_6D_four_model_clintox_source.csv",index=False,encoding="utf-8-sig")
    candidate_display={"rdkit_rf":"RF","gnn_gcn":"GCN","chemberta_mtr_linear_probe":"ChemBERTa","molformer_linear_probe":"MolFormer"}; y=np.arange(len(candidates))
    rel_metrics=[("mean_roc_auc","ROC-AUC",BLUE,"o",-.25),("mean_pr_auc","PR-AUC",TEAL,"D",-.15),("minority_recall","Recall",ORANGE,"o",-.05),("minority_false_negative_rate","FNR",RED,"s",.05),("mean_class_1_coverage","Coverage",PURPLE,"^",.15),("mean_set_size_mapped_1_to_2","Set size",GREY,"P",.25)]
    for yi,candidate in enumerate(candidates):
        row=dsource[dsource.candidate.eq(candidate)].iloc[0]
        dax.plot([0,1],[yi,yi],color=LIGHT,lw=.8,zorder=0); dax.add_patch(Rectangle((.5,yi+.005),.5,.09,fc=RED,ec="none",alpha=.055,zorder=0))
        for col,label,color,marker,offset in rel_metrics: dax.scatter(float(row[col]),yi+offset,color=color,marker=marker,s=24,zorder=3)
    dax.axvline(.9,color=PURPLE,lw=1.0,ls="--",zorder=1); dax.text(.885,len(candidates)-.45,"90% coverage target",ha="right",va="bottom",rotation=90,fontsize=8.0,color=PURPLE)
    dax.set(yticks=y,yticklabels=[candidate_display[c] for c in candidates],xlim=(0,1),ylim=(len(candidates)-.5,-1.40),xlabel="Metric value (set size mapped from 1-2 to 0-1)"); dax.grid(axis="x",color=LIGHT,lw=.7); dax.tick_params(axis="y",labelsize=8.0)
    discrimination=[Line2D([0],[0],marker=marker,ls="",color=color,label=label) for _,label,color,marker,_ in rel_metrics[:2]]
    minority=[Line2D([0],[0],marker=marker,ls="",color=color,label=label) for _,label,color,marker,_ in rel_metrics[2:]]
    leg1=dax.legend(handles=discrimination,title="Discrimination",loc="upper left",bbox_to_anchor=(0,.99),ncol=1,frameon=False,handletextpad=.25,borderpad=0)
    leg1.get_title().set_fontsize(8.5); leg1.get_title().set_fontweight("bold"); dax.add_artist(leg1)
    leg2=dax.legend(handles=minority,title="Minority safety",loc="upper right",bbox_to_anchor=(1,.99),ncol=2,frameon=False,handletextpad=.25,columnspacing=.55,borderpad=0)
    leg2.get_title().set_fontsize(8.5); leg2.get_title().set_fontweight("bold")
    save(fig,"Figure_6_prediction_errors_across_chemical_support")


if __name__ == "__main__":
    setup(); figure1(); figure2(); figure3(); figure4(); figure5(); figure6()
