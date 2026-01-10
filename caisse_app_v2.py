import streamlit as st
import streamlit as st

def gate():
    st.title("Accès sécurisé")
    pwd = st.text_input("Mot de passe", type="password")
    if pwd != st.secrets["APP_PASSWORD"]:
        st.stop()

gate()

st.set_page_config(page_title="Caisse 1000$ — Gestion du change", layout="centered")

# Toutes les dénominations (en cents)
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

TARGET_CENTS = 100000  # 1000.00$

def cents_to_str(c: int) -> str:
    return f"{c/100:.2f} $"

def total_cents(counts: dict) -> int:
    return sum(int(counts.get(k, 0)) * DENOMS[k] for k in DENOMS)

def add_counts(a: dict, b: dict) -> dict:
    return {k: int(a.get(k, 0)) + int(b.get(k, 0)) for k in DENOMS}

def sub_counts(a: dict, b: dict) -> dict:
    return {k: int(a.get(k, 0)) - int(b.get(k, 0)) for k in DENOMS}

def breakdown_table(counts: dict):
    rows = []
    for k in ORDER:
        q = int(counts.get(k, 0))
        rows.append({
            "Dénomination": k,
            "Valeur": f"{DENOMS[k]/100:.2f} $",
            "Quantité": q,
            "Total": f"{(q*DENOMS[k])/100:.2f} $",
        })
    return rows

st.title("Caisse 1000 $ — Gestion du change (v2)")
st.write("Workflow: **Total avant** → **Dépôt par type** → **Retrait par montants** (ex: 100$ en 5s) → **Total & composition finale**.")

st.divider()

# 1) CONTENU INITIAL
st.header("1) Contenu initial (AVANT)")
st.caption("Entre la quantité de chaque billet/pièce présent(e) dans la caisse avant l’opération.")

before = {}
c1, c2 = st.columns(2)
for i, k in enumerate(ORDER):
    with (c1 if i % 2 == 0 else c2):
        before[k] = st.number_input(f"{k} — quantité", min_value=0, step=1, value=0, key=f"b_{k}")

total_before = total_cents(before)
st.info(f"**TOTAL avant:** {cents_to_str(total_before)}")

if total_before != TARGET_CENTS:
    st.warning("⚠️ Le total avant n’est pas exactement 1 000,00 $. (Si votre règle est 'toujours 1000$', corrigez le contenu initial.)")

st.divider()

# 2) DEPOT (PAR TYPE)
st.header("2) Dépôt (ce que tu AJOUTES)")
st.caption("Choisis exactement ce que tu déposes (ex: 2 billets de 50$).")

deposit = {}
d1, d2 = st.columns(2)
for i, k in enumerate(ORDER):
    with (d1 if i % 2 == 0 else d2):
        deposit[k] = st.number_input(f"{k} — quantité déposée", min_value=0, step=1, value=0, key=f"d_{k}")

total_deposit = total_cents(deposit)
after_deposit = add_counts(before, deposit)
total_after_deposit = total_cents(after_deposit)

st.success(f"**TOTAL déposé:** {cents_to_str(total_deposit)}")
st.info(f"**TOTAL après dépôt:** {cents_to_str(total_after_deposit)}")

st.divider()

# 3) RETRAIT (CHANGE VOULU) PAR MONTANTS
st.header("3) Retrait (change voulu) — par montants")
st.caption("Ici tu écris des montants (en $) par dénomination. Exemple: 100$ en 5$ et 20$ en 10$.")
st.caption("L’app convertit automatiquement ces montants en quantités et vérifie la disponibilité.")

withdraw_counts = {k: 0 for k in DENOMS}
errors = []

w1, w2 = st.columns(2)
for i, k in enumerate(ORDER):
    with (w1 if i % 2 == 0 else w2):
        amt_dollars = st.number_input(f"{k} — montant à retirer ($)", min_value=0, step=5 if DENOMS[k] >= 500 else 1, value=0, key=f"wamt_{k}")
        amt_cents = int(amt_dollars) * 100
        denom = DENOMS[k]

        if amt_cents == 0:
            withdraw_counts[k] = 0
        else:
            if amt_cents % denom != 0:
                errors.append(f"{k}: {amt_dollars}$ n’est pas divisible par {denom/100:.2f}$.")
                withdraw_counts[k] = 0
            else:
                withdraw_counts[k] = amt_cents // denom

total_withdraw = total_cents(withdraw_counts)
st.info(f"**TOTAL retrait demandé:** {cents_to_str(total_withdraw)}")

# Vérifier dispo (après dépôt)
for k in ORDER:
    if withdraw_counts[k] > after_deposit[k]:
        errors.append(f"{k}: pas assez en caisse. Dispo après dépôt = {after_deposit[k]}, retrait demandé = {withdraw_counts[k]}.")

# (Option) règle d’équilibre: pour garder le total, retrait devrait = dépôt
if total_withdraw != total_deposit:
    st.warning("⚠️ Pour garder le total de la caisse inchangé, idéalement **retrait = dépôt**.")
    st.write(f"Dépôt: **{cents_to_str(total_deposit)}** | Retrait: **{cents_to_str(total_withdraw)}** | Diff: **{cents_to_str(total_deposit - total_withdraw)}**")

if errors:
    st.error("❌ Erreurs à corriger :")
    for e in errors:
        st.write(f"- {e}")

st.divider()

# 4) RÉSULTATS
st.header("4) Résultat final")
if st.button("CALCULER LE RÉSUMÉ FINAL"):
    if errors:
        st.error("Corrige d’abord les erreurs en section 3.")
    else:
        final_counts = sub_counts(after_deposit, withdraw_counts)
        total_final = total_cents(final_counts)

        st.subheader("Retrait à effectuer (en quantités)")
        for k in ORDER:
            q = int(withdraw_counts[k])
            if q:
                st.write(f"- **{q}** × {k} (= **{cents_to_str(q * DENOMS[k])}**)")

        st.subheader("Totaux")
        st.write(f"**Total avant:** {cents_to_str(total_before)}")
        st.write(f"**+ Dépôt:** {cents_to_str(total_deposit)}")
        st.write(f"**− Retrait:** {cents_to_str(total_withdraw)}")
        st.success(f"**Total final dans la caisse:** {cents_to_str(total_final)}")

        st.subheader("Composition finale de la caisse")
        st.table(breakdown_table(final_counts))

        if total_final == TARGET_CENTS:
            st.success("✅ Total final = 1 000,00 $")
        else:
            st.warning("⚠️ Total final ≠ 1 000,00 $. Si votre règle est 'toujours 1000$', ajustez dépôt/retrait.")

