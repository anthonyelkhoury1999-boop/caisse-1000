import streamlit as st
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

def rapport(open_c: dict, in_c: dict, out_c: dict, close_c: dict):
    rows = []
    t_open = t_in = t_out = t_close = 0

    for k in ORDER:
        o = int(open_c.get(k, 0))
        i = int(in_c.get(k, 0))
        out = int(out_c.get(k, 0))
        c = int(close_c.get(k, 0))

        rows.append({
            "Dénomination": k,
            "OPEN": o,
            "IN": i,
            "OUT": out,
            "CLOSE": c,
        })

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

# ---------- UI ----------
st.title("Rapport de caisse — 1000 $")
st.caption("Généré le " + datetime.now().strftime("%Y-%m-%d %H:%M"))
st.write("Remplis OPEN → IN → OUT (en **quantités**) → génère le rapport imprimable OPEN/IN/OUT/CLOSE.")

st.divider()

# OPEN
st.header("1) OPEN — Contenu initial")
open_counts = {}
c1, c2 = st.columns(2)
for i, k in enumerate(ORDER):
    with (c1 if i % 2 == 0 else c2):
        open_counts[k] = st.number_input(
            k,
            min_value=0,
            step=1,
            value=0,
            key=f"open_{k}"
        )

total_open = total_cents(open_counts)
st.info("TOTAL OPEN : " + cents_to_str(total_open))
if total_open != TARGET:
    st.warning("⚠️ Le TOTAL OPEN n’est pas 1 000,00 $. (Ce n’est pas bloquant, mais la caisse devrait normalement être à 1000$.)")

st.divider()

# IN
st.header("2) IN — Dépôt (quantités)")
in_counts = {}
d1, d2 = st.columns(2)
for i, k in enumerate(ORDER):
    with (d1 if i % 2 == 0 else d2):
        in_counts[k] = st.number_input(
            f"{k} (IN)",
            min_value=0,
            step=1,
            value=0,
            key=f"in_{k}"
        )

total_in = total_cents(in_counts)
after_in = add_counts(open_counts, in_counts)
total_after_in = total_cents(after_in)

st.info("TOTAL IN : " + cents_to_str(total_in))
st.success("TOTAL APRÈS IN : " + cents_to_str(total_after_in))

st.divider()

# OUT (FIXED) — QUANTITÉS
st.header("3) OUT — Retrait (quantités)")
st.caption("Entre des QUANTITÉS (ex: 3 billets de 10$, 20 pièces de 2$). Le total OUT inclut billets + monnaie.")

out_counts = {}
errors = []

w1, w2 = st.columns(2)
for i, k in enumerate(ORDER):
    with (w1 if i % 2 == 0 else w2):
        out_counts[k] = st.number_input(
            f"{k} — quantité à retirer",
            min_value=0,
            step=1,
            value=0,
            key=f"out_{k}"
        )

# validate and total
out_counts = {k: int(out_counts.get(k, 0)) for k in DENOMS}
total_out = total_cents(out_counts)
st.info("TOTAL OUT : " + cents_to_str(total_out))

for k in ORDER:
    if out_counts[k] > after_in[k]:
        errors.append(f"{k}: pas assez en caisse. Dispo après dépôt = {after_in[k]}, retrait demandé = {out_counts[k]}.")

st.divider()

# CLOSE + REPORT
st.header("4) CLOSE — Résultat final")

if st.button("GÉNÉRER LE RAPPORT"):
    if errors:
        st.error("Erreurs détectées :")
        for e in errors:
            st.write("- " + e)
    else:
        close_counts = sub_counts(after_in, out_counts)
        total_close = total_cents(close_counts)

        st.success("TOTAL CLOSE : " + cents_to_str(total_close))

        # Optional check: keep at 1000
        if total_close != TARGET:
            st.warning("⚠️ Le total final n’est pas 1 000,00 $. Si votre règle est 'toujours 1000$', ajuste OUT/IN.")
        else:
            st.success("✅ Total final = 1 000,00 $")

       st.subheader("Rapport imprimable — OPEN / IN / OUT / CLOSE")

report_data = rapport(open_counts, in_counts, out_counts, close_counts)

# Convert report to HTML table
html_rows = ""
for row in report_data:
    html_rows += "<tr>" + "".join(f"<td>{v}</td>" for v in row.values()) + "</tr>"

html_table = f"""
<div id="print-area">
  <h2>Rapport de caisse</h2>
  <table border="1" cellspacing="0" cellpadding="6">
    <thead>
      <tr>
        <th>Dénomination</th>
        <th>OPEN</th>
        <th>IN</th>
        <th>OUT</th>
        <th>CLOSE</th>
      </tr>
    </thead>
    <tbody>
      {html_rows}
    </tbody>
  </table>
</div>

<style>
@media print {{
  body * {{
    visibility: hidden;
  }}
  #print-area, #print-area * {{
    visibility: visible;
  }}
  #print-area {{
    position: absolute;
    left: 0;
    top: 0;
    width: 100%;
  }}
}}
</style>

<script>
function printReport() {{
  window.print();
}}
</script>
"""

st.markdown(html_table, unsafe_allow_html=True)

st.button("🖨️ Imprimer le rapport", on_click=lambda: st.markdown("<script>printReport();</script>", unsafe_allow_html=True))
