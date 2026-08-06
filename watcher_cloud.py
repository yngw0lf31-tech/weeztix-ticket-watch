#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Veille Weeztix « Regional Championships - September 5th » — GitHub Actions.
Lancée toutes les ~5 min par .github/workflows/watch.yml ; l'état
(state.json) est commité dans le repo entre deux exécutions.

NOTIFICATION UNIQUEMENT : aucune info personnelle ici, pas de réservation
automatique (ça, c'est le bot local en mode auto sur le Mac). Dès qu'une
place se libère :
  🚨 urgente — « PLACES DISPO » (rappel ~30 min tant que c'est en vente) ;
  ℹ️ info    — reparti en rupture, billetterie injoignable ≥ ~20 min.
"""
import json
import os
import random
import sys
import time
import unicodedata

from curl_cffi import requests

NTFY = "https://ntfy.sh"
TOPIC = os.environ.get("NTFY_TOPIC", "").strip()
if not TOPIC:
    sys.exit("NTFY_TOPIC manquant : configure le secret GitHub")

SHOP_GUID = "2267989d-8cc0-11f0-a9cb-7e126431635e"
TICKET_GUID = "b501ead1-7baf-48f5-af4c-fc16a0b05ddc"
TICKET_NAME = "Regional Championships - September 5th"
SHOP_URL = f"https://shop.weeztix.com/{SHOP_GUID}/tickets"
API_BASE = f"https://shop.api.openticket.tech/{SHOP_GUID}"

REMIND_SECONDS = 1800      # rappel « toujours dispo » (le bot local rappelle toutes les 5 min)
ERROR_ALERT_AFTER = 4      # runs consécutifs en erreur (~20 min) avant l'info

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")

s = requests.Session(impersonate="chrome")

def ascii_safe(t):
    return unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()

def push(title, msg, click, urgent):
    r = s.post(f"{NTFY}/{TOPIC}", data=msg.encode("utf-8"), headers={
        "Title": ascii_safe(title),
        "Priority": "urgent" if urgent else "default",
        "Tags": "rotating_light,tickets" if urgent else "information_source",
        "Click": click,
        "Actions": f"view, Ouvrir, {click}"}, timeout=20)
    print(f"ntfy {r.status_code} ← {title}")

def fetch_status():
    nocache = f"{int(time.time() * 1000)}-1-{random.randint(1, 999999999)}"
    r = s.get(f"{API_BASE}/data?nocache={nocache}", timeout=25, headers={
        "Accept": "application/json",
        "Origin": "https://shop.weeztix.com",
        "Referer": "https://shop.weeztix.com/"})
    if r.status_code != 200:
        raise RuntimeError(f"/data → HTTP {r.status_code}")
    t = (r.json().get("tickets") or {}).get(TICKET_GUID)
    if not isinstance(t, dict):
        raise RuntimeError("billet introuvable dans /data")
    return str(t.get("status") or "unknown")

# ── état ──────────────────────────────────────────────────────────────────
try:
    with open(STATE_FILE, encoding="utf-8") as f:
        st = json.load(f)
except (OSError, ValueError):
    st = {}

now = time.time()
try:
    statut = fetch_status()
except Exception as e:
    st["errors"] = st.get("errors", 0) + 1
    print(f"erreur ({st['errors']}) : {e}")
    if st["errors"] == ERROR_ALERT_AFTER and not st.get("error_alerted"):
        st["error_alerted"] = True
        push("Billetterie injoignable (GitHub)",
             f"Impossible de vérifier « {TICKET_NAME} » depuis ~20 min "
             "(depuis le cloud). Vérifie à la main au cas où.",
             SHOP_URL, False)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(st, f, indent=1)
    sys.exit(0)

old = st.get("status")
st["errors"], st["error_alerted"] = 0, False
if old and statut != old:
    print(f"statut : {old} → {statut}")

if statut == "available":
    first = old != "available"
    if first or now - st.get("last_alert", 0) >= REMIND_SECONDS:
        st["last_alert"] = now
        push("PLACES DISPO ! (GitHub)",
             f"« {TICKET_NAME} » est EN VENTE (38 €) — fonce : {SHOP_URL} "
             "(Si ton Mac est allumé, le bot local est peut-être déjà en train "
             "de réserver.)", SHOP_URL, True)
elif old == "available":
    push("Repasse complet (GitHub)",
         f"« {TICKET_NAME} » est de nouveau épuisé.", SHOP_URL, False)

st["status"] = statut
with open(STATE_FILE, "w", encoding="utf-8") as f:
    json.dump(st, f, indent=1)

if "--hello" in sys.argv:
    push("Veille cloud OK (GitHub)",
         f"Test réussi — GitHub Actions surveille « {TICKET_NAME} » toutes "
         f"les ~5 min, Mac allumé ou pas. Statut actuel : {statut}.",
         SHOP_URL, False)

print(f"OK — statut : {statut}")
