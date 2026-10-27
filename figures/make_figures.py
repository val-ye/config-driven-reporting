"""Draw the article's figures with Graphviz.

Usage: python figures/make_figures.py
Needs the `dot` command (Graphviz). Writes figures/fig*.png and fig*.svg.
"""
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
FONT = "Inter"
INK, MUTED, LINE = "#1f2937", "#6b7280", "#9ca3af"
TEAL, TEAL_BG = "#0f766e", "#e6f4f1"
AMBER, AMBER_BG = "#b45309", "#fdf3e7"
GREY_BG = "#f3f4f6"

COMMON = f'''
  graph [fontname="{FONT}", fontsize=13, fontcolor="{INK}", bgcolor="white", pad=0.3, nodesep=0.35, ranksep=0.5];
  node  [fontname="{FONT}", fontsize=12, fontcolor="{INK}", shape=box, style="rounded,filled",
         fillcolor="{GREY_BG}", color="{LINE}", penwidth=1.2, margin="0.18,0.08"];
  edge  [fontname="{FONT}", fontsize=10, color="{LINE}", penwidth=1.2, arrowsize=0.7];
'''


def fig1_before() -> str:
    clients = ["Client N", "Juniper", "PulseFit", "BrewBox"]  # Graphviz stacks LR rows bottom-up here
    rows = "\n".join(
        f'b{i} [label="{c}"]; r{i} [label=<{c} report<BR/><FONT POINT-SIZE="10" COLOR="{AMBER}">own copy of every formula</FONT>>, '
        f'fillcolor="{AMBER_BG}", color="{AMBER}"]; b{i} -> r{i};'
        for i, c in enumerate(clients))
    return f'''digraph G {{ {COMMON}
  rankdir=LR; label=<<B>Before</B>: a report per client<BR/> >; labelloc=t; labeljust=l; fontsize=15;
  {rows}
}}'''


def fig1_after() -> str:
    clients = ["BrewBox", "PulseFit", "Juniper", "Client N"]
    rows = "\n".join(
        f'a{i} [label="{c}"]; s{i} [label="settings", shape=note, style=filled, fillcolor="white", '
        f'fontsize=10, fontcolor="{MUTED}"]; a{i} -> s{i} [arrowhead=none]; s{i} -> res;'
        for i, c in enumerate(clients))
    return f'''digraph G {{ {COMMON}
  rankdir=LR; label=<<B>After</B>: one model, one catalog, one template<BR/> >; labelloc=t; labeljust=l; fontsize=15;
  {rows}
  model [label=<<B>One model</B><BR/><FONT POINT-SIZE="10">fact table at a fixed grain</FONT>>, fillcolor="{TEAL_BG}", color="{TEAL}"];
  cat   [label=<<B>One metric catalog</B><BR/><FONT POINT-SIZE="10">each metric defined once</FONT>>, fillcolor="{TEAL_BG}", color="{TEAL}"];
  res   [label=<<B>Resolver</B><BR/><FONT POINT-SIZE="10">fills KPI slots per client</FONT>>, fillcolor="white", color="{TEAL}"];
  tmpl  [label=<<B>One report template</B><BR/><FONT POINT-SIZE="10">KPI 1 ... KPI N</FONT>>, fillcolor="{TEAL_BG}", color="{TEAL}"];
  {{rank=same; model; cat; res;}}
  model -> res; cat -> res; res -> tmpl [color="{TEAL}", penwidth=1.6];
}}'''


def fig2() -> str:
    def table(name, rows, accent=TEAL, bg=TEAL_BG, note=""):
        body = "".join(f'<TR><TD ALIGN="LEFT" BALIGN="LEFT">{r}</TD></TR>' for r in rows)
        foot = f'<TR><TD ALIGN="LEFT"><FONT POINT-SIZE="10" COLOR="{MUTED}">{note}</FONT></TD></TR>' if note else ""
        return (f'<<TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="5" COLOR="{accent}" BGCOLOR="white">'
                f'<TR><TD BGCOLOR="{bg}" ALIGN="LEFT"><B>{name}</B></TD></TR>{body}{foot}</TABLE>>')
    measures = ["spend", "impressions", "sessions", "conversions", "revenue"]
    fact = table("fact_daily_performance",
                 ["<I>date, client, campaign, channel</I>"] + measures,
                 note="grain: client x campaign x channel x day<BR/>additive measures only, no ratios")
    return f'''digraph G {{ {COMMON}
  rankdir=LR; node [shape=plaintext, style="", margin=0];
  fact   [label={fact}];
  date     [label={table("dim_date", ["date", "day of week"], LINE, GREY_BG)}];
  client   [label={table("dim_client", ["client"], LINE, GREY_BG)}];
  campaign [label={table("dim_campaign", ["campaign", "client", "channel"], LINE, GREY_BG)}];
  channel  [label={table("dim_channel", ["channel (media type)"], LINE, GREY_BG)}];
  cfg [shape=note, style="filled,dashed", fillcolor="{AMBER_BG}", color="{AMBER}", margin="0.18,0.1",
       label=<<B>Client settings</B> (outside the model)<BR ALIGN="LEFT"/>KPI types, what it sends,<BR ALIGN="LEFT"/>what it calls each metric,<BR ALIGN="LEFT"/>conversion name, week start<BR ALIGN="LEFT"/>>];
  {{rank=same; date; client;}}
  {{rank=same; campaign; channel;}}
  date -> fact [arrowhead=none]; client -> fact [arrowhead=none];
  fact -> campaign [arrowhead=none]; fact -> channel [arrowhead=none];
  cfg -> client [style=dashed, color="{AMBER}", label=<<FONT POINT-SIZE="10" COLOR="{AMBER}">  one record per client</FONT>>];
}}'''


def fig3() -> str:
    def chips(items, strike=()):
        cells = []
        for it in items:
            if it in strike:
                cells.append(f'<TD BGCOLOR="white" BORDER="1" COLOR="{AMBER}" STYLE="ROUNDED"><FONT COLOR="{AMBER}"><S>{it}</S></FONT></TD>')
            else:
                cells.append(f'<TD BGCOLOR="{TEAL_BG}" BORDER="1" COLOR="{TEAL}" STYLE="ROUNDED">{it}</TD>')
        return "".join(cells)
    template = ["spend", "conversions", "cpa", "sessions", "cvr"]
    return f'''digraph G {{ {COMMON}
  rankdir=TB; ranksep=0.4; node [shape=plaintext, style="", margin=0];
  cfg [label=<<TABLE BORDER="1" COLOR="{AMBER}" CELLBORDER="0" CELLPADDING="6" BGCOLOR="{AMBER_BG}">
    <TR><TD ALIGN="LEFT"><B>PulseFit settings</B></TD></TR>
    <TR><TD ALIGN="LEFT"><FONT FACE="DejaVu Sans Mono" POINT-SIZE="11">kpi_types: [cpa]<BR ALIGN="LEFT"/>conversion: Install<BR ALIGN="LEFT"/>sends: [spend, impressions, conversions]<BR ALIGN="LEFT"/></FONT></TD></TR></TABLE>>];
  cat [label=<<TABLE BORDER="1" COLOR="{LINE}" CELLBORDER="0" CELLPADDING="6" BGCOLOR="{GREY_BG}">
    <TR><TD ALIGN="LEFT"><B>Metric catalog</B></TD></TR>
    <TR><TD ALIGN="LEFT"><FONT FACE="DejaVu Sans Mono" POINT-SIZE="11">cpa: spend / conversions<BR ALIGN="LEFT"/>cvr: conversions / sessions<BR ALIGN="LEFT"/></FONT></TD></TR></TABLE>>];
  check [label=<<TABLE BORDER="0" CELLSPACING="6" CELLPADDING="5">
    <TR><TD ALIGN="LEFT" WIDTH="190"><B>1. Wanted</B><BR ALIGN="LEFT"/><FONT POINT-SIZE="10" COLOR="{MUTED}">its cpa template</FONT><BR ALIGN="LEFT"/></TD>{chips(template)}</TR>
    <TR><TD ALIGN="LEFT" WIDTH="190"><B>2. Supported?</B><BR ALIGN="LEFT"/><FONT POINT-SIZE="10" COLOR="{MUTED}">each metric's inputs vs<BR ALIGN="LEFT"/>what the client sends</FONT><BR ALIGN="LEFT"/></TD>{chips(template, strike=("sessions", "cvr"))}</TR>
  </TABLE>>];
  out [label=<<TABLE BORDER="1" COLOR="{TEAL}" CELLBORDER="0" CELLPADDING="6" BGCOLOR="white">
    <TR><TD ALIGN="LEFT" COLSPAN="3"><B>3. PulseFit's report</B></TD></TR>
    <TR><TD BGCOLOR="{TEAL_BG}">KPI 1: Spend</TD><TD BGCOLOR="{TEAL_BG}">KPI 2: Installs</TD><TD BGCOLOR="{TEAL_BG}">KPI 3: Cost per Install</TD></TR>
    <TR><TD ALIGN="LEFT" COLSPAN="3"><FONT POINT-SIZE="10" COLOR="{AMBER}">Not shown: Sessions, Conversion rate (they need sessions, which this client does not send)</FONT></TD></TR></TABLE>>];
  {{rank=same; cfg; cat;}}
  cfg -> check; cat -> check [style=dashed]; check -> out [color="{TEAL}", penwidth=1.6];
}}'''


def render(name: str, dot_src: str) -> None:
    (HERE / f"{name}.dot").write_text(dot_src)
    for fmt, extra in (("png", ["-Gdpi=200"]), ("svg", [])):
        subprocess.run(["dot", f"-T{fmt}", *extra, "-o", str(HERE / f"{name}.{fmt}"),
                        str(HERE / f"{name}.dot")], check=True)
    (HERE / f"{name}.dot").unlink()
    print(f"wrote figures/{name}.png and .svg")


def combine(name: str, parts: list[str]) -> None:
    """Place PNG panels side by side, tops aligned, with a thin divider."""
    from PIL import Image, ImageDraw
    imgs = [Image.open(HERE / f"{p}.png").convert("RGB") for p in parts]
    gap = 120
    w = sum(i.width for i in imgs) + gap * (len(imgs) - 1)
    h = max(i.height for i in imgs)
    out = Image.new("RGB", (w, h), "white")
    x = 0
    for k, im in enumerate(imgs):
        out.paste(im, (x, 0))
        x += im.width
        if k < len(imgs) - 1:
            ImageDraw.Draw(out).line([(x + gap // 2, 60), (x + gap // 2, h - 60)], fill="#e5e7eb", width=4)
            x += gap
    out.save(HERE / f"{name}.png")
    for p in parts:
        (HERE / f"{p}.png").unlink()
    print(f"wrote figures/{name}.png (panels: {', '.join(parts)}; SVGs kept separately)")


if __name__ == "__main__":
    render("fig1_before", fig1_before())
    render("fig1_after", fig1_after())
    combine("fig1_before_after", ["fig1_before", "fig1_after"])
    render("fig2_model", fig2())
    render("fig3_resolve", fig3())
