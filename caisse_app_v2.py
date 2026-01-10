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

TARGET = 100000  # 1000 $

def cents_to_str(c):
    return f"{c/100:.2f} $"

def total_cents(counts):
    return sum(int(counts.get(k, 0)) * DENOMS[k] for k in DENOMS)

def add_counts(a, b):
    return {k: int(a.get(k, 0)) + int(b.get(k, 0)) for k in DENOMS}

def sub_counts(a, b):
    return {k: int(a.get(k, 0)) - int(b.get(k, 0)) for k in DENOMS}

def rapport(open_c, in_c, out_c, close_c):
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

st.title("Rapport de caisse — 1000 $")
st.caption("Généré le " + datetime.now().strftime("%Y-%m-%d %H:%M"))

st.divider()

# OPEN
st.header("1) OPEN — Contenu initial")
open_counts = {}
c1, c2 = st.columns(2)
for i, k in enumerate(ORDER):
    with (c1 if i % 2 == 0 else c2):
        open_counts[k] = st.number_input(k, min_value=0, step=1, value=0, key=f"o_{k}")

total_open = total_cents(open_counts)
st.info("TOTAL OPEN : " + cents_to_str(total_open))

st.divider()

# IN
st.header("2) IN — Dépôt")
in_counts = {}
d1, d2 = st.columns(2)
for i, k in enumerate(ORDER):
    with (d1 if i % 2 == 0 else d2):
        in_counts[k] = st.number_input(f"{k} (IN)", min_value=0, step=1, value=0, key=f"in_{k}")

total_in = total_cents(in_counts)
st.info("TOTAL IN : " + cents_to_str(total_in))

after_in = add_counts(open_counts, in_counts)

st.divider()

# OUT
st.header("3) OUT — Retrait (montants)")
out_counts = {}
errors = []
w1, w2 = st.columns(2)

for i, k in enumerate(ORDER):
    with (w1 if i % 2 == 0 else w2):
        amt = st.number_input(
            f"{k} — montant $",
            min_value=0,
            step=5 if DENOMS[k] >= 500 else 1,
            value=0,
            key=f"out_{k}"
        )
        cents = int(amt) * 100
        if cents % DENOMS[k] != 0:
            errors.append(f"{k}: montant invalide")
            out_counts[k] = 0
        else:
            out_counts[k] = cents // DENOMS[k]

total_out = total_cents(out_counts)
st.info("TOTAL OUT : " + cents_to_str(total_out))

for k in ORDER:
    if out_counts[k] > after_in[k]:
        errors.append(f"{k}: pas assez en caisse")

st.divider()

# CLOSE
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

        if total_close != TARGET:
            st.warning("⚠️ Le total final n’est pas 1 000 $")

        st.subheader("Rapport OPEN / IN / OUT / CLOSE")
        st.table(rapport(open_counts, in_counts, out_counts, close_counts))

        st.caption("🖨️ Impression : Ctrl/Cmd + P → Imprimer ou Sauvegarder en PDF")
