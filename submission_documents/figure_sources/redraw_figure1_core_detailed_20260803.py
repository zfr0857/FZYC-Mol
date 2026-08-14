from __future__ import annotations

from pathlib import Path
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Rectangle


OUT = Path(r"D:\fzyc\output\paper43_jcheminform_completion_20260726\Figure1_core_detailed_variant_20260803")

INK = "#171B1E"
GREY = "#747A7E"
LIGHT = "#DDE3E6"
BLUE = "#356D99"
ORANGE = "#D8802B"
TEAL = "#278F88"
PURPLE = "#75629A"
RED = "#B45A51"
GREEN = "#6C9F77"
PALE_BLUE = "#EAF2F8"
PALE_ORANGE = "#FBEEDF"
PALE_TEAL = "#E7F3F1"
PALE_PURPLE = "#F0EDF6"
PALE_RED = "#F7E7E4"
PALE_GREEN = "#E8F0E5"
PALE_GREY = "#F2F3F4"
FLOW_COLOR = "#747A7E"
FLOW_WIDTH = .90
FLOW_SCALE = 8


def setup():
    mpl.rcParams.update({
        "font.family": "Times New Roman",
        "font.serif": ["Times New Roman"],
        "font.size": 8.0,
        "mathtext.fontset": "custom",
        "mathtext.rm": "Times New Roman",
        "mathtext.it": "Times New Roman:italic",
        "mathtext.bf": "Times New Roman:bold",
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "svg.fonttype": "none",
        "savefig.facecolor": "white",
        "figure.facecolor": "white",
    })


def build():
    setup()
    # A slightly taller canvas keeps the enlarged typography airy while
    # preserving a journal-friendly single-column aspect ratio.
    fig, ax = plt.subplots(figsize=(7.2, 4.45))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    def txt(x, y, s, size=8.5, weight="normal", color=INK, ha="center", va="center",
            rotation=0, z=8, linespacing=1.0):
        return ax.text(x, y, s, fontsize=max(8.4, size), fontfamily="Times New Roman",
                       fontweight=weight, color=color, ha=ha, va=va, rotation=rotation,
                       zorder=z, linespacing=linespacing)

    def outer(x, y, w, h, label, title, badge_color, title_size=10.6):
        ax.add_patch(FancyBboxPatch((x, y), w, h,
                                    boxstyle="round,pad=.005,rounding_size=.014",
                                    fc="white", ec=INK, lw=1.05,
                                    linestyle=(0, (1.2, 1.5)), zorder=1))
        ax.add_patch(Circle((x+.023, y+h-.028), .0175, fc=badge_color, ec="white",
                            lw=.55, zorder=6))
        txt(x+.023, y+h-.028, str(label), size=10.2, weight="bold", color="white")
        txt(x+.050, y+h-.028, title, size=title_size, weight="bold", ha="left")

    def card(x, y, w, h, fill, title, color=INK):
        ax.add_patch(FancyBboxPatch((x, y), w, h,
                                    boxstyle="round,pad=.004,rounding_size=.009",
                                    fc=fill, ec=mpl.colors.to_rgba(color, .24),
                                    lw=.42, zorder=2))
        txt(x+w/2, y+h-.018, title, size=9.0, weight="bold", color=color,
            va="top", linespacing=.96)

    def arrow(x1, y1, x2, y2, color=INK, width=.8, scale=8, z=6):
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>",
                                     mutation_scale=scale, lw=width, color=color, zorder=z))

    def flow_arrow(x1, y1, x2, y2, z=7):
        """One geometry and colour for every workflow connector."""
        arrow(x1, y1, x2, y2, color=FLOW_COLOR, width=FLOW_WIDTH,
              scale=FLOW_SCALE, z=z)

    def matrix(x, y, n=4, cell=.010, color=PURPLE, offset=0):
        vals = np.roll(np.arange(n*n).reshape(n, n), offset, axis=1)
        for rr in range(n):
            for cc in range(n):
                a = .18 + .70 * vals[rr, cc] / max(n*n-1, 1)
                ax.add_patch(Rectangle((x+cc*cell, y+(n-1-rr)*cell), cell*.92, cell*.92,
                                       fc=mpl.colors.to_rgba(color, a), ec="white", lw=.25, zorder=4))

    def molecule(x, y, color=BLUE, r=.023):
        pts = np.array([[x-r,y],[x-r*.45,y+r*.72],[x+r*.45,y+r*.72],
                        [x+r,y],[x+r*.45,y-r*.72],[x-r*.45,y-r*.72]])
        ax.plot(*np.vstack([pts, pts[0]]).T, color=color, lw=.9, zorder=4)
        ax.scatter(pts[:,0], pts[:,1], s=8, fc="white", ec=color, lw=.6, zorder=5)

    # Five major modules.
    outer(.035, .700, .365, .275, "A", "Data and Candidate Registry", BLUE)
    outer(.420, .700, .545, .275, "B", "Repeated Nested Scaffold Selection", PURPLE)
    outer(.035, .350, .930, .310, "C", "Frozen References and Completion-Gap Decomposition", TEAL)
    # Match the C-to-D/E vertical gutter (0.040) to the A/B-to-C gutter.
    outer(.035, .080, .555, .230, "D", "Robustness and Chemical Support", ORANGE)
    outer(.610, .080, .355, .230, "E", "Auditable Evidence and Reporting", GREEN, title_size=10.3)

    # Module 1: only the information needed to define the registry.
    card(.052, .725, .145, .190, PALE_BLUE, "Endpoint registration", BLUE)
    molecule(.090, .818, BLUE)
    for i in range(3):
        ax.add_patch(Rectangle((.126+i*.006, .795+i*.007), .040, .046,
                               fc="white", ec=BLUE, lw=.65, zorder=4))
    txt(.124, .755, "9 endpoints\ncurated · no overlap", linespacing=1.04)

    card(.211, .725, .172, .190, PALE_ORANGE, "Fixed candidate registry", ORANGE)
    ys = [.825, .801, .777, .753]
    for i, (yy, k, col) in enumerate(zip(ys, [4,8,16,32], [BLUE,TEAL,ORANGE,PURPLE])):
        xs = np.linspace(.232, .303, 2+i)
        ax.plot(xs, [yy]*len(xs), color=LIGHT, lw=1.0, zorder=3)
        ax.scatter(xs, [yy]*len(xs), s=10, fc=col, ec="white", lw=.3, zorder=4)
        txt(.319, yy, f"K = {k}", color=PURPLE, ha="left")
    txt(.297, .736, "32 candidates · fixed order")

    # Module 2: detailed nested-selection pipeline.
    steps = [
        ("Outer/inner\npartitions", PALE_BLUE, BLUE),
        ("Fold-specific\npreprocessing", PALE_GREEN, GREEN),
        ("Inner-validation\nranking", PALE_PURPLE, PURPLE),
        ("Freeze decision\n+ outer audit", PALE_ORANGE, ORANGE),
    ]
    x0, y0, w, h, gap = .444, .748, .116, .144, .012
    for i, (label, fill, col) in enumerate(steps):
        xx = x0 + i*(w+gap)
        ax.add_patch(FancyBboxPatch((xx,y0),w,h,boxstyle="round,pad=.003,rounding_size=.008",
                                    fc=fill, ec=col, lw=.55, zorder=2))
        txt(xx+w/2, y0+h-.020, label, weight="bold", color=col, va="top", linespacing=.95)
        if i == 0:
            for j in range(3):
                ax.add_patch(Rectangle((xx+.018+j*.010,y0+.035+j*.007),.031,.017,
                                       fc="white",ec=col,lw=.5,zorder=4))
            for j in range(3):
                ax.add_patch(Circle((xx+.066+j*.014,y0+.049),.007,fc="white",ec=col,lw=.55,zorder=4))
        elif i == 1:
            matrix(xx+.038,y0+.035,n=3,cell=.012,color=col)
        elif i == 2:
            ax.plot([xx+.025,xx+.090],[y0+.040,y0+.067],color=col,lw=.9,zorder=4)
            ax.scatter([xx+.025,xx+.047,xx+.069,xx+.090],[y0+.040,y0+.053,y0+.048,y0+.067],s=10,fc=col,zorder=5)
        else:
            ax.add_patch(Rectangle((xx+.022,y0+.037),.035,.037,fc="white",ec=col,lw=.7,zorder=4))
            ax.plot([xx+.029,xx+.050],[y0+.055,y0+.055],color=col,lw=1.0,zorder=5)
            ax.scatter([xx+.077,xx+.092],[y0+.050,y0+.066],s=12,fc=[BLUE,TEAL],zorder=5)
        if i < len(steps)-1:
            flow_arrow(xx+w+.001,y0+h/2,xx+w+gap-.001,y0+h/2)
    txt(.693, .718, "10 split seeds · 3 outer scaffold folds · selection confined to training data",
        color=GREY)

    # Module 3: the main conceptual contribution, expanded in full.
    # Raise the three reference cards slightly to reserve a dedicated formula band.
    # This prevents the red decomposition bracket from crossing either equation.
    card(.055, .445, .250, .165, PALE_ORANGE, "Validation-selected candidate", ORANGE)
    card(.375, .445, .250, .165, PALE_PURPLE, "K-dependent within-prefix reference", PURPLE)
    card(.695, .445, .250, .165, PALE_TEAL, "K-invariant full-registry reference", TEAL)

    # Candidate representations and audit metric.
    for cx, col, lab in [(.180, ORANGE, r"$\hat{j}_u(K)$"), (.500, PURPLE, r"$j_{ref}^{dep}(-s,K)$"), (.820, TEAL, r"$j_{ref}^{inv}(-s)$")]:
        for i in range(4):
            ax.add_patch(Rectangle((cx-.045+i*.023,.504),.019,.040,
                                   fc=mpl.colors.to_rgba(col,.25+.16*i),ec="white",lw=.35,zorder=4))
        # Place the three audit markers above the candidate bars. Keeping the
        # marker row away from the mathematical label prevents collisions with
        # the dep/inv superscripts in Word and PDF rendering.
        ax.scatter([cx-.046,cx,cx+.046],[.553,.553,.553],s=11,
                   fc=[BLUE,TEAL,ORANGE],ec="white",lw=.4,zorder=5)
        txt(cx, .462, lab, size=9.0, weight="bold", color=col)

    # The two adjacent gaps and their full-registry sum.
    arrow(.305,.535,.375,.535,color=PURPLE,width=1.0,scale=9)
    txt(.340,.558,r"$G_{dep}$",weight="bold",color=PURPLE)
    txt(.340,.509,"within-prefix\nselection",color=PURPLE,linespacing=.95)
    arrow(.625,.535,.695,.535,color=TEAL,width=1.0,scale=9)
    txt(.660,.558,r"$G_{avail}$",weight="bold",color=TEAL)
    txt(.660,.509,"candidate\navailability",color=TEAL,linespacing=.95)
    ax.add_patch(FancyBboxPatch((.352,.352),.296,.069,
                                boxstyle="round,pad=.003,rounding_size=.008",
                                fc=mpl.colors.to_rgba(RED,.055),
                                ec=mpl.colors.to_rgba(RED,.18),lw=.35,zorder=2))
    ax.plot([.180,.180,.820,.820],[.445,.427,.427,.445],color=RED,lw=1.0,zorder=4)
    txt(.500,.410,r"$G_{inv}=G_{avail}+G_{dep}$",size=9.2,weight="bold",color=RED)
    txt(.500,.371,r"$\Delta_{inv}=\frac{1}{S}\sum_s[G_{inv}(s,32)-G_{inv}(s,4)]$",
        size=8.7,color=INK)

    # Module 4: four diagnostics within one coherent robustness block.
    robustness = [
        (.052,.112,.128,.153,PALE_PURPLE,"Ranking &\nequivalence",PURPLE),
        (.185,.112,.128,.153,PALE_BLUE,"Utility-pattern\ndiversity",BLUE),
        (.318,.112,.128,.153,PALE_ORANGE,"Transfer &\ncomposition",ORANGE),
        (.451,.112,.132,.153,PALE_GREEN,"Chemical support\n& error audit",GREEN),
    ]
    for x,y,w,h,fill,title,col in robustness:
        card(x,y,w,h,fill,title,col)
    # Ranking.
    for i in range(4):
        ax.plot([.073,.150],[.183-i*.014,.178-i*.009],color=GREY,lw=.65,zorder=3)
    ax.scatter([.073]*4,[.183-i*.014 for i in range(4)],s=8,fc=BLUE,zorder=4)
    ax.scatter([.150]*4,[.178-i*.009 for i in range(4)],s=8,fc=ORANGE,zorder=4)
    txt(.115,.131,"CAHit@3 · τ",color=PURPLE)
    # Diversity.
    for i in range(3): matrix(.203+i*.032,.160,n=3,cell=.008,color=PURPLE,offset=i)
    txt(.253,.131,"rank · entropy",color=BLUE)
    # Transfer/composition.
    ax.plot([.337,.412],[.185,.185],color=LIGHT,lw=1.2,zorder=3)
    ax.scatter(np.linspace(.337,.412,4),[.185]*4,s=9,fc=ORANGE,zorder=4)
    ax.scatter([.345,.376,.407],[.155,.164,.146],s=[10,15,20],fc=[PURPLE,TEAL,ORANGE],zorder=4)
    txt(.391,.128,"split · equal size",color=ORANGE)
    # Support/error.
    for i,fill in enumerate(["#F2D9D5","#EDEFD0","#D6E7D5"]):
        ax.add_patch(Rectangle((.467+i*.034,.154),.030,.043,fc=fill,ec="white",lw=.4,zorder=3))
        molecule(.482+i*.034,.173,GREEN,.009)
    txt(.532,.128,"novel · error · FN",color=GREEN)

    # Module 5: evidence trail, deliberately simple.
    evidence = [
        ("Inner and outer probabilities", BLUE),
        ("Eligibility and frozen identities", TEAL),
        ("Splits, settings and hashes", ORANGE),
        ("Failures and uncertainty", RED),
        ("Machine-readable release", PURPLE),
    ]
    for i,(label,col) in enumerate(evidence):
        yy=.258-i*.026
        ax.scatter([.663],[yy],s=14,fc=col,zorder=4)
        ax.plot([.681,.713],[yy,yy],color=LIGHT,lw=1.7,zorder=3)
        txt(.715,yy,label,ha="left",color=INK)
    ax.add_patch(FancyBboxPatch((.678,.100),.240,.036,boxstyle="round,pad=.003,rounding_size=.008",
                                fc=PALE_PURPLE,ec=PURPLE,lw=.6,zorder=2))
    txt(.798,.118,"Auditable decision record",weight="bold",color=PURPLE)

    # Main process arrows.
    flow_arrow(.692,.698,.692,.662)
    # Two branch connectors span the same-size gutter used between A/B and C.
    # They sit away from the central endpoint-level contrast formula.
    flow_arrow(.312,.348,.312,.311)
    flow_arrow(.788,.348,.788,.311)
    flow_arrow(.401,.835,.419,.835)
    flow_arrow(.592,.205,.608,.205)

    # Bottom ribbon.
    ribbon=[(.055,.215,"Registry"),(.235,.410,"Nested selection"),(.430,.635,"Gap decomposition"),
            (.655,.805,"Robustness"),(.825,.950,"Reporting")]
    for x1,x2,label in ribbon:
        txt((x1+x2)/2,.056,label,size=9.3,weight="bold")
        flow_arrow(x1,.031,x2,.031)

    for artist in fig.findobj(match=mpl.text.Text):
        artist.set_fontfamily("Times New Roman")
        if artist.get_fontsize()<8.4: artist.set_fontsize(8.4)
        # Keep the rightmost diagnostic label centered inside its compact card.
        if artist.get_text().startswith("novel"):
            artist.set_position((.517, .128))

    OUT.mkdir(parents=True,exist_ok=True)
    fig.subplots_adjust(0,0,1,1)
    fig.savefig(OUT/"Figure1_core_detailed.pdf",bbox_inches="tight",pad_inches=.015)
    fig.savefig(OUT/"Figure1_core_detailed.svg",bbox_inches="tight",pad_inches=.015)
    fig.savefig(OUT/"Figure1_core_detailed_600dpi.png",dpi=600,bbox_inches="tight",pad_inches=.015)
    plt.close(fig)


if __name__ == "__main__":
    build()
