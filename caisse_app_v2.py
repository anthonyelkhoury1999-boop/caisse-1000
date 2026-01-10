import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime

st.set_page_config(page_title="Caisse 1000$ — Rapport", layout="centered")

DENOMS = {
    "Billet 100 $": 10000,
    "Billet 50 $": 5000,
    "Billet 20 $": 2000,
    "Billet 10 $": 1000,
    "Billet 5 $": 500,
    "Pièce 2 $": 200,
    "Pièce 1 $": 100,
    "Pièce 0,25 $": 25,
    "Pièce 0,10 $": 10,
    "Pièce 0,05 $": 5,
}

ORDER = [
    "Billet 100 $", "Billet 50 $", "Billet 20 $", "Billet 10 $", "Billet 5 $",
    "Pièce 2 $", "Pièce 1 $", "Pièce 0,25 $", "Pièce 0,10 $", "Pièce 0,05 $"
]

TARGET = 100000  # 1000.00 $

def cents_to_str(c: int) -> str:
    return f"{c/100:.2f} $"

def total_cents(counts: dict) -> int:
    return sum(int(counts.get(k, 0)) * DENOMS[k] for k in DENOMS)

def add_counts(a: dict, b: dict) -> dict:
    return {k: int(a.get(k, 0)) + int(b.get(k, 0)) for k in DENOMS}

def sub_counts(a: dict, b: dict) -> dict:
    return {k: int(a.get(k, 0)) - int(b.get(k, 0)) for k in DENOMS}

def rapport_rows(open_c: dict, in_c: dict, out_c: dict, close_c: dict):
    rows = []
    t_open = t_in = t_out = t_close = 0

    for k in ORDER:
        o = int(open_c.get(k, 0))
        i = int(in_c.get(k, 0))
        out = int(out_c.get(k, 0))
        c = int(close_c.get(k, 0))

        rows.append({"Dénomination": k, "OPEN": o, "IN": i, "OUT": out, "CLOSE": c})

        t_open += o * DENOMS[k]
        t_in += i * DENOMS[k]
        t_out += out * DENOMS[k]
        t_close += c * DENOMS[k]

    rows.append({
        "Dénomination": "TOTAL ($)",
        "OPEN": f"{t_open/100:.2f}",
        "IN": f"{t_in/100:.2f}",
        "OUT": f"{t_out/100:.2f}",
        "CLOSE": f"{t_close/100:.2f}",
    })

    return rows

def build_report_html(rows, meta_title: str):
    # Build HTML table rows
    body_rows = ""
    for r in rows:
        body_rows += (
            "<tr>"
            f"<td>{r['Dénomination']}</td>"
            f"<td>{r['OPEN']}</td>"
            f"<td>{r['IN']}</td>"
            f"<td>{r['OUT']}</td>"
            f"<td>{r['CLOSE']}</td>"
            "</tr>"
        )

    # Main report HTML (this is what we want to print)
    report_inner = f"""
      <div>
        <h2 style="margin:0;">Rapport de caisse</h2>
        <div style="opacity:0.75; font-size:12px; margin-top:4px;">{meta_title}</div>
      </div>
      <div style="height:12px;"></div>
      <table style="width:100%; border-collapse:collapse; font-size:14px; background:#ffffff; color:#000000;" border="1" cellpadding="6" cellspacing="0">
        <thead>
          <tr style="background:#f3f3f3; color:#000;">
            <th>Dénomination</th>
            <th>OPEN</th>
            <th>IN</th>
            <th>OUT</th>
            <th>CLOSE</th>
          </tr>
        </thead>
        <tbody>
          {body_rows}
        </tbody>
      </table>
    """

    # Escape backticks so JS string doesn't break
    report_inner_js = report_inner.replace("`", "\\`")

    # Full component HTML with a REAL print button (no Streamlit rerun)
    html = f"""
    <div id="report-wrapper" style="font-family: Arial, sans-serif;">
      <div style="display:flex; align-items:center; justify-content:space-between; gap:12px;">
        <div>
          <h3 style="margin:0;">Aperçu du rapport</h3>
          <div style="opacity:0.7; font-size:12px;">Clique le bouton pour imprimer seulement le tableau.</div>
        </div>
        <button id="print-btn" style="
            padding:10px 14px;
            border-radius:10px;
            border:1px solid #ccc;
            cursor:pointer;
            font-weight:600;
            background:white;
          ">
          🖨️ Imprimer le rapport
        </button>
      </div>

      <div style="height:10px;"></div>

      <div id="report">
        {report_inner}
      </div>
    </div>

    <script>
      function printOnlyReport() {{
        var reportHtml = `{report_inner_js}`;
        var w = window.open('', '_blank', 'width=900,height=700');
        w.document.open();
        w.document.write('<html><head><title>Rapport de caisse</title>');
        w.document.write('<style>');
        w.document.write('body{{font-family:Arial,sans-serif;padding:18px;}}');
        w.document.write('table{{width:100%;border-collapse:collapse;}}');
        w.document.write('th,td{{border:1px solid #000;padding:6px;}}');
        w.document.write('th{{background:#f3f3f3;}}');
        w.document.write('</style>');
        w.document.write('</head><body>');
        w.document.write(reportHtml);
        w.document.write('</body></html>');
        w.document.close();
        w.focus();
        w.print();
      }}

      const btn = document.getElementById('print-btn');
      if (btn) {{
        btn.addEventListener('click', function() {{
          printOnlyReport();
        }});
      }}
    </script>
    """
    return html

# ---------------- STATE ----------------
if "show_report" not in st.session_state:
    st.session_state.show_report = False
if "report_payload" not in st.session_state:
    st.session_state.report_payload = None

# ---------------- UI ----------------
st.title("Caisse 1000 $ — OPEN / IN / OUT / CLOSE")
st.caption("OUT = quantités. Le bouton d’impression imprime uniquement le rapport.")

st.divider()

# OPEN
st.header("1) OPEN — Contenu initial")
open_counts = {}
c1, c2 = st.columns(2)
for i, k in enumerate(ORDER):
    with (c1 if i % 2 == 0 else c2):
        open_counts[k] = st.number_input(k, min_value=0, step=1, value=0, key=f"open_{k}")

st.info("TOTAL OPEN : " + cents_to_str(total_cents(open_counts)))

st.divider()

# IN
st.header("2) IN — Dépôt (quantités)")
in_counts = {}
d1, d2 = st.columns(2)
for i, k in enumerate(ORDER):
    with (d1 if i % 2 == 0 else d2):
        in_counts[k] = st.number_input(f"{k} (IN)", min_value=0, step=1, value=0, key=f"in_{k}")

after_in = add_counts(open_counts, in_counts)
st.info("TOTAL IN : " + cents_to_str(total_cents(in_counts)))
st.success("TOTAL APRÈS IN : " + cents_to_str(total_cents(after_in)))

st.divider()

# OUT
st.header("3) OUT — Retrait (quantités)")
out_counts = {}
w1, w2 = st.columns(2)
for i, k in enumerate(ORDER):
    with (w1 if i % 2 == 0 else w2):
        out_counts[k] = st.number_input(f"{k} — quantité à retirer", min_value=0, step=1, value=0, key=f"out_{k}")

out_counts = {k: int(out_counts.get(k, 0)) for k in DENOMS}
st.info("TOTAL OUT : " + cents_to_str(total_cents(out_counts)))

errors = []
for k in ORDER:
    if out_counts[k] > after_in[k]:
        errors.append(f"{k}: pas assez en caisse. Dispo après dépôt = {after_in[k]}, retrait demandé = {out_counts[k]}.")

st.divider()

# CLOSE + REPORT
st.header("4) CLOSE — Résultat final")
colA, colB = st.columns([1, 1])

with colA:
    generate = st.button("GÉNÉRER LE RAPPORT")
with colB:
    clear = st.button("EFFACER LE RAPPORT")

if clear:
    st.session_state.show_report = False
    st.session_state.report_payload = None

if generate:
    if errors:
        st.session_state.show_report = False
        st.session_state.report_payload = None
        st.error("Erreurs détectées :")
        for e in errors:
            st.write("- " + e)
    else:
        close_counts = sub_counts(after_in, out_counts)
        total_close = total_cents(close_counts)

        rows = rapport_rows(open_counts, in_counts, out_counts, close_counts)
        meta = "Généré le " + datetime.now().strftime("%Y-%m-%d %H:%M")

        st.session_state.report_payload = {
            "rows": rows,
            "meta": meta,
            "total_close": total_close
        }
        st.session_state.show_report = True

if st.session_state.show_report and st.session_state.report_payload:
    total_close = st.session_state.report_payload["total_close"]
    st.success("TOTAL CLOSE : " + cents_to_str(total_close))

    if total_close != TARGET:
        st.warning("⚠️ Le total final n’est pas 1 000,00 $.")
    else:
        st.success("✅ Total final = 1 000,00 $")

    st.subheader("Rapport (impression du tableau seulement)")
    html = build_report_html(
        st.session_state.report_payload["rows"],
        st.session_state.report_payload["meta"]
    )
    components.html(html, height=560, scrolling=True)
