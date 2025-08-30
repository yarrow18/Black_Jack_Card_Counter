#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import ttk, messagebox
import math, random, threading

APP_TITLE = "Blackjack Counter — PRO"

# --------- Counting systems ---------
HI_LO   = {'2':+1,'3':+1,'4':+1,'5':+1,'6':+1,'7':0,'8':0,'9':0,'T':-1,'J':-1,'Q':-1,'K':-1,'A':-1}
ZEN     = {'2':+1,'3':+1,'4':+2,'5':+2,'6':+2,'7':+1,'8':0,'9':0,'T':-2,'J':-2,'Q':-2,'K':-2,'A':0}
OMEGA2  = {'2':+1,'3':+1,'4':+2,'5':+2,'6':+2,'7':+1,'8':0,'9':-1,'T':-2,'J':-2,'Q':-2,'K':-2,'A':0}  # ace-neutral
HIOPT2  = {'2':+1,'3':+1,'4':+2,'5':+2,'6':+1,'7':+1,'8':0,'9':0,'T':-2,'J':-2,'Q':-2,'K':-2,'A':0}   # ace-neutral

SYSTEMS = [
    ("Hi-Lo", HI_LO),
    ("Zen", ZEN),
    ("Omega II", OMEGA2),
    ("Hi-Opt II", HIOPT2),
]

# --- Utility sets (micro-optimization for readability) ---
TEN_RANKS = ('T','J','Q','K')
UP_3456   = ('3','4','5','6')
UP_456    = ('4','5','6')
UP_56     = ('5','6')
UP_23456  = ('2','3','4','5','6')
UP_79TJQKA = ('7','9','T','J','Q','K','A')

# --- Illustrious 18 + Fab 4 override (Hi-Lo, multi-decks approx) ---
def apply_indices_override(total, soft, up, first_two, can_double, tc_floor, rules):
    """Return 'D','S','H','SUR' or None based on indices."""
    # Fab 4 (Late Surrender)
    if rules.get("LS", False) and first_two and not soft:
        if total == 15 and up == 'T' and tc_floor >= 0: return 'SUR'
        if total == 15 and up == '9' and tc_floor >= 2: return 'SUR'
        if total == 15 and up == 'A' and tc_floor >= 1: return 'SUR'
        if total == 14 and up == 'T' and tc_floor >= 3: return 'SUR'

    # Doubling guard for D10
    def dbl_ok(t):
        return can_double and (not rules.get("D10", False) or t in (10,11))

    # Soft exceptions (I18)
    if soft:
        # A,8 vs 6: Double at +1 else Stand (respects D10)
        if total == 19 and up == '6' and first_two and dbl_ok(19) and tc_floor >= 1:
            if not rules.get("D10", False):
                return 'D'
            else:
                return None
        return None

    # Illustrious 18 (hard)
    if total == 16 and up == 'T':                    return 'S' if tc_floor >= 0 else None
    if total == 15 and up == 'T':                    return 'S' if tc_floor >= 4 else None
    if total == 10 and up in TEN_RANKS and first_two and dbl_ok(10):
                                                    return 'D' if tc_floor >= 4 else None
    if total == 12 and up == '3':                    return 'S' if tc_floor >= 2 else None
    if total == 12 and up == '2':                    return 'S' if tc_floor >= 3 else None
    if total == 11 and up == 'A' and first_two and dbl_ok(11):
                                                    return 'D' if tc_floor >= 1 else None
    if total == 9  and up == '2' and first_two and dbl_ok(9):
                                                    return 'D' if tc_floor >= 1 else None
    if total == 10 and up == 'A' and first_two and dbl_ok(10):
                                                    return 'D' if tc_floor >= 4 else None
    if total == 9  and up == '7' and first_two and dbl_ok(9):
                                                    return 'D' if tc_floor >= 3 else None
    if total == 16 and up == '9':                    return 'S' if tc_floor >= 5 else None

    # Negative indices (default Stand -> Hit if TC too low)
    if total == 13 and up == '2':                    return 'H' if tc_floor < -1 else None
    if total == 13 and up == '3':                    return 'H' if tc_floor < -2 else None
    if total == 12 and up == '4':                    return 'H' if tc_floor < 0  else None
    if total == 12 and up == '5':                    return 'H' if tc_floor < -2 else None
    if total == 12 and up == '6':                    return 'H' if tc_floor < -1 else None

    # 12 vs 7: Stand at +3 (else base = Hit)
    if total == 12 and up == '7':                    return 'S' if tc_floor >= 3 else None

    return None

CARD_ORDER = ['2','3','4','5','6','7','8','9','T','J','Q','K','A']
DISPLAY = {'2':'2','3':'3','4':'4','5':'5','6':'6','7':'7','8':'8','9':'9','T':'10','J':'J','Q':'Q','K':'K','A':'A'}

# --------- Linear EV: base & slope (≈) ---------
BASE_ANCHOR_6D_S17_DAS = -0.36  # %
ADJ_H17    = -0.20
ADJ_NO_DAS = -0.14
ADJ_RSA    = +0.03
ADJ_LS     = +0.08
ADJ_NO_PEEK= -0.11

DECK_ADJ = {1:+0.25, 2:+0.17, 4:+0.06, 6:0.0, 8:-0.03, 10:-0.05, 12:-0.06}
SLOPE = {
    "Hi-Lo":    {1:0.65, 2:0.60, 4:0.53, 6:0.50, 8:0.47, 10:0.45, 12:0.44},
    "Zen":      {1:0.70, 2:0.65, 4:0.56, 6:0.53, 8:0.50, 10:0.48, 12:0.46},
    "Omega II": {1:0.72, 2:0.67, 4:0.58, 6:0.55, 8:0.52, 10:0.50, 12:0.48},
    "Hi-Opt II":{1:0.73, 2:0.68, 4:0.60, 6:0.56, 8:0.53, 10:0.51, 12:0.49},
}
ACE_PENALTY = 0.90  # penalty if no Ace side-count (ΩII / Hi-Opt II)

INS_THRESH_HILO = +3  # TC floor threshold for insurance (simple fallback)
MIN_DECKS_DEN = 0.25  # min 1/4 shoe to stabilize TC near the cut

# --- Illustrious 18 + Fab 4 display (not used by logic, kept) ---
I18_F4 = [
    ("Insurance", +3, "Take", "Don't take"),
    ("16 vs 10",  0,  "Stand",   "Hit"),
    ("15 vs 10", +4,  "Stand",   "Hit"),
    ("10 vs 10", +4,  "Double",  "Hit"),
    ("12 vs 3",  +2,  "Stand",   "Hit"),
    ("12 vs 2",  +3,  "Stand",   "Hit"),
    ("11 vs A",  +1,  "Double",  "Hit"),
    ("9  vs 2",  +1,  "Double",  "Hit"),
    ("10 vs A",  +4,  "Double",  "Hit"),
    ("9  vs 7",  +3,  "Double",  "Hit"),
    ("16 vs 9",  +5,  "Stand",   "Hit"),
    ("13 vs 2", -1,   "Stand",   "Hit"),
    ("12 vs 4",  0,   "Stand",   "Hit"),
    ("12 vs 5", -2,   "Stand",   "Hit"),
    ("12 vs 6", -1,   "Stand",   "Hit"),
    ("13 vs 3", -2,   "Stand",   "Hit"),
    ("12 vs 7", +3,   "Hit",     "Stand"),
    ("A,8 vs 6", +1,  "Double",  "Stand"),
    # Fab 4 (LS)
    ("15 vs 10 (Sur)", +0, "Surrender", "Hit"),
    ("15 vs 9 (Sur)",  +2, "Surrender", "Hit"),
    ("15 vs A (Sur)",  +1, "Surrender", "Hit"),
    ("14 vs 10 (Sur)", +3, "Surrender", "Hit"),
]

# --------- Utils ---------
RANK_VALUE = {'2':2,'3':3,'4':4,'5':5,'6':6,'7':7,'8':8,'9':9,'T':10,'J':10,'Q':10,'K':10,'A':11}

def up_to_val(up):
    return 11 if up=='A' else 10 if up in TEN_RANKS else int(up)

def hand_total(cards):
    total = sum(11 if c=='A' else 10 if c in TEN_RANKS else int(c) for c in cards)
    aces = sum(1 for c in cards if c=='A')
    while total > 21 and aces > 0:
        total -= 10
        aces -= 1
    soft = (aces > 0)  # at least one Ace still counts as 11
    return total, soft

def is_blackjack(cards):
    return len(cards)==2 and ('A' in cards) and any(c in TEN_RANKS for c in cards)

def copy_counts(rem):
    return {r:int(rem.get(r,0)) for r in CARD_ORDER}

def draw_one(counts, rnd):
    tot = sum(counts[r] for r in CARD_ORDER)
    if tot<=0: return 'T'
    pick = rnd.randrange(tot)
    s=0
    for r in CARD_ORDER:
        s += counts[r]
        if pick < s:
            counts[r]-=1
            return r
    return 'T'

def should_split(rank, up, rules):
    """Basic strategy pairs (multi-deck). Correctly handles DAS / non-DAS."""
    das = rules.get("DAS", True)
    if rank == 'A' or rank == '8':
        return True
    if rank in TEN_RANKS:
        return False
    if rank == '9':
        # Split 9s vs 2–6,8,9 (not vs 7,T,A)
        return up not in ('7',) + TEN_RANKS + ('A',)
    if rank == '7':
        # With DAS: 2–7 ; without DAS: 2–6
        return (up in UP_23456) or (das and up == '7')
    if rank == '6':
        # With DAS: 2–6 ; without DAS: 3–6
        return (up in UP_23456) if das else (up in ('3','4','5','6'))
    if rank in ('2','3'):
        # With DAS: 2–7 ; without DAS: 4–7
        return (up in UP_23456 + ('7',)) if das else (up in ('4','5','6','7'))
    if rank == '4':
        # Only with DAS vs 5–6
        return das and (up in UP_56)
    return False

def hard_action(t, up, rules, can_double):
    def can_dbl(total):
        return can_double and (not rules.get("D10", False) or total in (10, 11))
    if t >= 17:
        return 'S'
    if t >= 13 and up_to_val(up) <= 6:
        return 'S'
    if t == 12 and up in ('4', '5', '6'):
        return 'S'
    # 11: double vs 2–10 uniquement (vs As -> Hit sauf index +1)
    if t == 11 and can_dbl(11) and up != 'A':
        return 'D'
    # 10: double vs 2–9 uniquement (vs 10/As -> Hit sauf index)
    if t == 10 and can_dbl(10) and up_to_val(up) <= 9:
        return 'D'
    if t == 9 and can_dbl(9) and up in UP_3456:
        return 'D'
    return 'H'

def soft_action(t, up, rules, can_double):
    def can_dbl(total):
        return can_double and (not rules.get("D10", False) or total in (10, 11))
    if t >= 19:
        return 'S'
    if t == 18:
        # A,7 : Double vs 3–6 ; Stand vs 2/7/8 ; Hit vs 9/T/A
        if up in UP_3456 and can_dbl(18):
            return 'D'
        if up in ('2', '7', '8'):
            return 'S'
        return 'H'
    if t == 17 and can_dbl(17) and up in UP_3456:
        return 'D'
    if t == 16 and can_dbl(16) and up in ('4', '5', '6'):
        return 'D'
    if t == 15 and can_dbl(15) and up in ('4', '5', '6'):
        return 'D'
    if t == 14 and can_dbl(14) and up in UP_56:
        return 'D'
    if t == 13 and can_dbl(13) and up in UP_56:
        return 'D'
    return 'H'

def estimate_base_edge(decks, h17, das, rsa, hsa, dos, d10, ls, peek):
    base = BASE_ANCHOR_6D_S17_DAS + DECK_ADJ.get(int(decks), 0.0)
    if h17:  base += ADJ_H17
    if not das: base += ADJ_NO_DAS
    if rsa:  base += ADJ_RSA
    if ls:   base += ADJ_LS
    if not peek: base += ADJ_NO_PEEK
    return round(base,2)

def slope_for(system,decks,side_ace_used):
    decks = max(1, min(12, int(decks)))
    dkeys = sorted(SLOPE[system].keys())
    nearest = min(dkeys, key=lambda k: abs(k - decks))
    m = SLOPE[system][nearest]
    if system in ("Omega II","Hi-Opt II") and not side_ace_used:
        m *= ACE_PENALTY
    return round(m,2)

# --------- Dealer play ---------
def dealer_play(cards, counts, rules, rnd):
    while True:
        tot, soft = hand_total(cards)
        must_hit = (tot < 17) or (tot == 17 and soft and rules.get("H17", False))
        if not must_hit: break
        cards.append(draw_one(counts, rnd))
    return hand_total(cards)[0]

# --------- Resolution (ENHC/OBO exact) ---------
def resolve_vs_dealer(p, up, dealer_hole, counts, rules, rnd, doubled=False):
    # ENHC: dealer BJ revealed at end -> doubles/splits lose all (except OBO original bet).
    if (not rules["PEEK"]) and (dealer_hole is not None) and is_blackjack([up, dealer_hole]):
        if rules["OBO"]:
            return -1.0
        return -2.0 if doubled else -1.0

    tot, _ = hand_total(p)
    if tot > 21:
        return -2.0 if doubled else -1.0

    # PEEK: USE the already-drawn hole card
    if rules["PEEK"]:
        dealer_cards = [up, dealer_hole] if dealer_hole is not None else [up, draw_one(counts, rnd)]
    else:
        dealer_cards = [up, dealer_hole] if dealer_hole is not None else [up]

    dealer_total = dealer_play(dealer_cards, counts, rules, rnd)

    if dealer_total > 21: return +2.0 if doubled else +1.0
    if tot > dealer_total: return +2.0 if doubled else +1.0
    if tot < dealer_total: return -2.0 if doubled else -1.0
    return 0.0

def resolve_vs_dealer_stand(p, up, dealer_hole, counts, rules, rnd):
    if (not rules["PEEK"]) and (dealer_hole is not None) and is_blackjack([up, dealer_hole]):
        return -1.0
    tot, _ = hand_total(p)
    if tot > 21: return -1.0
    if rules["PEEK"]:
        dealer_cards = [up, dealer_hole] if dealer_hole is not None else [up, draw_one(counts, rnd)]
    else:
        dealer_cards = [up, dealer_hole] if dealer_hole is not None else [up]
    dealer_total = dealer_play(dealer_cards, counts, rules, rnd)
    if dealer_total > 21: return +1.0
    if tot > dealer_total: return +1.0
    if tot < dealer_total: return -1.0
    return 0.0

# --------- Player ---------
def play_hand(p, up, dealer_hole, counts, rules, rnd, tc_floor, apply_idx, split_depth=0, can_double=True, can_split=True):
    first_two = (len(p) == 2)
    tot, soft = hand_total(p)
    # Index first (may recommend Stand/Double or Surrender)
    override = apply_indices_override(tot, soft, up, first_two, can_double, tc_floor, rules) if apply_idx else None
    if rules["LS"] and first_two and override == 'SUR' and not (p[0] == '8' and p[1] == '8'):
        return -0.5
    if can_split and first_two:
    # ENHC + OBO: if the dealer has BJ, only the original bet is lost (split bet refunded)
        if (not rules["PEEK"]) and (dealer_hole is not None) and is_blackjack([up, dealer_hole]) and rules["OBO"]:
            return -1.0
        r1 = 'T' if p[0] in TEN_RANKS else p[0]
        r2 = 'T' if p[1] in TEN_RANKS else p[1]
        if r1==r2 and should_split(r1, up, rules) and split_depth<3:
            if r1=='A':
                ev=0.0
                for _ in range(2):
                    hand=['A', draw_one(counts,rnd)]
                    if not rules["HSA"]:
                        # If doubling allowed on split Aces but no hit: 1 card then stand, counted as a 'double'.
                        if rules["DOUBLE_ON_SPLIT_ACES"]:
                            ev += resolve_vs_dealer(hand, up, dealer_hole, counts, rules, rnd, doubled=True)
                        else:
                            ev += resolve_vs_dealer_stand(hand, up, dealer_hole, counts, rules, rnd)
                    else:
                        ev+=play_hand(hand, up, dealer_hole, counts, rules, rnd, tc_floor, apply_idx,
                                      split_depth=split_depth+1,
                                      can_double=(rules["DOUBLE_ON_SPLIT_ACES"]),
                                      can_split=(rules["RSA"] and split_depth<3))
                return ev
            else:
                ev=0.0
                for _ in range(2):
                    hand=[r1, draw_one(counts,rnd)]
                    ev+=play_hand(hand, up, dealer_hole, counts, rules, rnd, tc_floor, apply_idx,
                                  split_depth=split_depth+1,
                                  can_double=rules["DAS"],
                                  can_split=True)
                return ev
    # (light recompute if the hand changed)
    tot, soft = hand_total(p)
    # Base surrender – only if no index forced Stand/Double, and not 8,8
    if override is None and rules["LS"] and first_two and not soft and not (p[0] == '8' and p[1] == '8'):
        if (tot == 16 and up in ('9', 'T', 'J', 'Q', 'K', 'A')) or (tot == 15 and up == 'T'):
            return -0.5
    if override=='D' and can_double:
        p.append(draw_one(counts,rnd))
        return resolve_vs_dealer(p, up, dealer_hole, counts, rules, rnd, doubled=True)
    act = override if override in ('H','S') else (soft_action(tot, up, rules, can_double) if soft else hard_action(tot, up, rules, can_double))
    if act=='D' and can_double:
        p.append(draw_one(counts,rnd))
        return resolve_vs_dealer(p, up, dealer_hole, counts, rules, rnd, doubled=True)
    while True:
        tot,soft = hand_total(p)
        if tot>=21: break
        a = soft_action(tot, up, rules, False) if soft else hard_action(tot, up, rules, False)
        if a=='H':
            p.append(draw_one(counts,rnd)); continue
        else: break
    return resolve_vs_dealer(p, up, dealer_hole, counts, rules, rnd, doubled=False)

# --- Forced-first-action variant for advice ---
def play_hand_forced_first(p, up, dealer_hole, counts, rules, rnd, tc_floor, apply_idx, force, split_depth=0):
    first_two = (len(p)==2)
    if force == 'SURRENDER' and rules["LS"] and first_two and not (p[0]=='8' and p[1]=='8'):
        return -0.5
    if force == 'SPLIT' and first_two:
    # ENHC + OBO: same logic in "Compare" mode
        if (not rules["PEEK"]) and (dealer_hole is not None) and is_blackjack([up, dealer_hole]) and rules["OBO"]:
            return -1.0
        r1 = 'T' if p[0] in TEN_RANKS else p[0]
        r2 = 'T' if p[1] in TEN_RANKS else p[1]
        if r1==r2 and split_depth<3:
            if r1=='A':
                ev=0.0
                for _ in range(2):
                    hand=['A', draw_one(counts,rnd)]
                    if not rules["HSA"]:
                        # If doubling allowed on split Aces but no hit: 1 card then stand, counted as a 'double'.
                        if rules["DOUBLE_ON_SPLIT_ACES"]:
                            ev += resolve_vs_dealer(hand, up, dealer_hole, counts, rules, rnd, doubled=True)
                        else:
                            ev += resolve_vs_dealer_stand(hand, up, dealer_hole, counts, rules, rnd)
                    else:
                        ev+=play_hand(hand, up, dealer_hole, counts, rules, rnd, tc_floor, apply_idx,
                                      split_depth=split_depth+1,
                                      can_double=(rules["DOUBLE_ON_SPLIT_ACES"]),
                                      can_split=(rules["RSA"] and split_depth<3))
                return ev
            else:
                ev=0.0
                for _ in range(2):
                    hand=[r1, draw_one(counts,rnd)]
                    ev+=play_hand(hand, up, dealer_hole, counts, rules, rnd, tc_floor, apply_idx,
                                  split_depth=split_depth+1,
                                  can_double=rules["DAS"],
                                  can_split=True)
                return ev
    if force == 'DOUBLE':
        p2=p[:]; p2.append(draw_one(counts,rnd))
        return resolve_vs_dealer(p2, up, dealer_hole, counts, rules, rnd, doubled=True)
    if force == 'STAND':
        return resolve_vs_dealer_stand(p, up, dealer_hole, counts, rules, rnd)
    if force == 'HIT':
        p2=p[:]; p2.append(draw_one(counts,rnd))
        return play_hand(p2, up, dealer_hole, counts, rules, rnd, tc_floor, apply_idx, split_depth=split_depth)
    return play_hand(p, up, dealer_hole, counts, rules, rnd, tc_floor, apply_idx, split_depth=split_depth)

# --------- Monte Carlo / EOR ---------
def simulate_ev(rem_counts, rules, hands=20000, seed=12345, tc_floor=0, apply_idx=True):
    rnd = random.Random(seed)
    total=0.0; total2=0.0
    for _ in range(hands):
        ev = simulate_one_hand(rem_counts, rules, rnd, tc_floor, apply_idx)
        total += ev; total2 += ev*ev
    mean = (total/hands)*100.0
    var  = max(1e-9, ((total2/hands) - (total/hands)**2))
    return mean, var

def simulate_one_hand(rem_counts, rules, rnd, tc_floor, apply_idx):
    counts = copy_counts(rem_counts)
    p=[draw_one(counts,rnd)]; up=draw_one(counts,rnd); p.append(draw_one(counts,rnd))
    hole = draw_one(counts, rnd)  # always drawn (even in ENHC)
    player_bj = is_blackjack(p)
    ins_ev=0.0
    if up=='A':
        tens = counts['T']+counts['J']+counts['Q']+counts['K']
        denom = sum(counts[r] for r in CARD_ORDER); p_bj=(tens/denom) if denom>0 else 0.0
        take = (tc_floor>=INS_THRESH_HILO) or (p_bj>1/3.0)
        if rules["PEEK"]:
            if is_blackjack([up,hole]): 
                ins_ev += +1.0 if take else 0.0
                return (0.0 if player_bj else -1.0)+ins_ev
            else:
                ins_ev += -0.5 if take else 0.0
        # ENHC: many casinos do not offer insurance -> leave ins_ev=0 if PEEK=False

    if rules["PEEK"]:
        if up in TEN_RANKS and hole=='A': return (0.0 if player_bj else -1.0)+ins_ev
        if player_bj: return (1.5 if rules["BJ_3_2"] else 1.2)+ins_ev
        ev = play_hand(p, up, hole, counts, rules, rnd, tc_floor, apply_idx, split_depth=0, can_double=True, can_split=True)
        return ev + ins_ev
    else:
        if player_bj: return (1.5 if rules["BJ_3_2"] else 1.2)+ins_ev
        ev_player = play_hand(p, up, hole, counts, rules, rnd, tc_floor, apply_idx, split_depth=0, can_double=True, can_split=True)
        return ev_player + ins_ev

def calibrate_eor(rem_counts, rules, hands=10000, seed=789, tc_floor=0, apply_idx=True):
    base,_ = simulate_ev(rem_counts, rules, hands=hands, seed=seed, tc_floor=tc_floor, apply_idx=apply_idx)
    eor = {}
    for r in CARD_ORDER:
        if rem_counts.get(r,0)<=0: eor[r]=0.0; continue
        c2 = copy_counts(rem_counts); c2[r]-=1
        ev2,_ = simulate_ev(c2, rules, hands=max(2000,hands//2), seed=seed+hash(r)%99991, tc_floor=tc_floor, apply_idx=apply_idx)
        eor[r] = ev2 - base
    return base, eor

def simulate_fixed_action(rem_counts, rules, player_cards, dealer_up, hands=8000, seed=42, tc_floor=0, apply_idx=True, force='AUTO'):
    rnd = random.Random(seed); total_ev=0.0
    for _ in range(hands):
        counts = copy_counts(rem_counts)
        for c in player_cards:
            if counts.get(c,0)>0: counts[c]-=1
        if counts.get(dealer_up,0)>0: counts[dealer_up]-=1
        hole = draw_one(counts, rnd)  # always drawn
        if rules["PEEK"] and is_blackjack([dealer_up,hole]): 
            total_ev += (0.0 if is_blackjack(player_cards) else -1.0)
            continue
        if is_blackjack(player_cards): 
            total_ev += (1.5 if rules["BJ_3_2"] else 1.2)
            continue
        total_ev += play_hand_forced_first(player_cards[:], dealer_up, hole, counts, rules, rnd, tc_floor, apply_idx, force)
    return (total_ev/hands)*100.0

# ---------------- Scrollable Frame ----------------
class VerticalScrolledFrame(ttk.Frame):
    def __init__(self, parent, *args, **kw):
        super().__init__(parent, *args, **kw)
        canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        vscroll = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.interior = ttk.Frame(canvas)

        interior_id = canvas.create_window((0, 0), window=self.interior, anchor="nw")
        canvas.configure(yscrollcommand=vscroll.set)

        def _configure_interior(event):
            size = (self.interior.winfo_reqwidth(), self.interior.winfo_reqheight())
            canvas.config(scrollregion="0 0 %s %s" % size)
            if self.interior.winfo_reqwidth() != canvas.winfo_width():
                canvas.config(width=self.interior.winfo_reqwidth())

        def _configure_canvas(event):
            if self.interior.winfo_reqwidth() != canvas.winfo_width():
                canvas.itemconfigure(interior_id, width=canvas.winfo_width())

        self.interior.bind('<Configure>', _configure_interior)
        canvas.bind('<Configure>', _configure_canvas)

        canvas.pack(side="left", fill="both", expand=True)
        vscroll.pack(side="right", fill="y")

# -------------- GUI ---------
class ProApp:
    def __init__(self, root):
        self.root = root
        root.title(APP_TITLE)

        # Scrollable container
        scroller = VerticalScrolledFrame(root)
        scroller.pack(fill="both", expand=True)
        self.page = scroller.interior  # parent for all content

        # State
        self.decks_var = tk.IntVar(value=6)
        self.pen_var   = tk.IntVar(value=75)
        # Rules
        self.h17_var = tk.BooleanVar(value=True)
        self.das_var = tk.BooleanVar(value=True)
        self.rsa_var = tk.BooleanVar(value=True)
        self.hsa_var = tk.BooleanVar(value=False)
        self.dos_var = tk.BooleanVar(value=True)   # DOUBLE ON SPLIT ACES
        self.d10_var = tk.BooleanVar(value=False)  # Double only 10/11
        self.peek_var= tk.BooleanVar(value=True)
        self.enhc_var= tk.BooleanVar(value=False)  # when True -> peek False
        self.obo_var = tk.BooleanVar(value=False)  # ENHC Original Bets Only
        self.bj32_var= tk.BooleanVar(value=True)   # True=3:2 else 6:5
        self.ls_var  = tk.BooleanVar(value=True)
        self.asc_var = tk.BooleanVar(value=False)

        # Indexes / sim / EOR
        self.apply_idx_var = tk.BooleanVar(value=True)
        self.hands_var = tk.IntVar(value=20000)
        self.hands_eor_var = tk.IntVar(value=12000)

        self.cards_seen = {r:0 for r in CARD_ORDER}
        self.history = []

        # EOR model
        self.eor_base_ev = None
        self.eor_vec = None
        self.eor_ref_counts = None
        self.ace_tc_weight = 0.0

        self._build_controls()
        self._build_table()
        self._build_mid_notebook()
        self._build_ev_panel()
        self._build_status()

        self.update_all()

        
        # --- Key shortcuts to add cards (ignored when typing in inputs) ---
        def _key_add_handler(rank):
            def _h(e):
                w = self.root.focus_get()
                try:
                    wc = w.winfo_class() if w else ""
                except Exception:
                    wc = ""
                # Ignore if focus is on text inputs / selectors
                if wc in ("TEntry","Entry","TCombobox","TSpinbox","Text"):
                    return
                self.add_card(rank)
            return _h

        for key, rank in [('2','2'),('3','3'),('4','4'),('5','5'),('6','6'),
                          ('7','7'),('8','8'),('9','9'),
                          ('0','T'),('t','T'),('T','T'),
                          ('j','J'),('J','J'),('q','Q'),('Q','Q'),('k','K'),('K','K'),
                          ('a','A'),('A','A')]:
            root.bind(key, _key_add_handler(rank))

    def _build_controls(self):
        box = ttk.LabelFrame(self.page, text="Rules & shoe")
        box.pack(fill="x", padx=8, pady=6)
        ttk.Label(box, text="# decks").grid(row=0, column=0, sticky="w", padx=6)
        ttk.Spinbox(box, from_=1, to=12, textvariable=self.decks_var, width=6, justify="center").grid(row=0, column=1)
        ttk.Label(box, text="Penetration %").grid(row=0, column=2, sticky="w", padx=6)
        ttk.Spinbox(box, from_=30, to=100, textvariable=self.pen_var, width=6, justify="center").grid(row=0, column=3)

        ttk.Checkbutton(box, text="H17", variable=self.h17_var, command=self.update_all).grid(row=0, column=4, padx=6)
        ttk.Checkbutton(box, text="DAS", variable=self.das_var, command=self.update_all).grid(row=0, column=5, padx=6)
        ttk.Checkbutton(box, text="RSA", variable=self.rsa_var, command=self.update_all).grid(row=0, column=6, padx=6)
        ttk.Checkbutton(box, text="Hit Split Aces", variable=self.hsa_var, command=self.update_all).grid(row=0, column=7, padx=6)
        ttk.Checkbutton(box, text="Double on split Aces", variable=self.dos_var, command=self.update_all).grid(row=0, column=8, padx=6)

        ttk.Checkbutton(box, text="D10 (double 10/11 only)", variable=self.d10_var, command=self.update_all).grid(row=1, column=0, padx=6, sticky="w")
        ttk.Checkbutton(box, text="Peek (hole-card)", variable=self.peek_var, command=self._sync_peek_enhc).grid(row=1, column=1, padx=6, sticky="w")
        ttk.Checkbutton(box, text="ENHC (no hole-card)", variable=self.enhc_var, command=self._sync_peek_enhc).grid(row=1, column=2, padx=6, sticky="w")
        ttk.Checkbutton(box, text="OBO (original bet only)", variable=self.obo_var, command=self.update_all).grid(row=1, column=3, padx=6, sticky="w")
        ttk.Checkbutton(box, text="BJ 3:2 (otherwise 6:5)", variable=self.bj32_var, command=self.update_all).grid(row=1, column=4, padx=6, sticky="w")
        ttk.Checkbutton(box, text="Late Surrender", variable=self.ls_var, command=self.update_all).grid(row=1, column=5, padx=6, sticky="w")
        ttk.Checkbutton(box, text="Side-count Aces (ΩII/Hi-Opt II)", variable=self.asc_var, command=self.update_all).grid(row=1, column=6, padx=6, sticky="w")

        cardbox = ttk.LabelFrame(self.page, text="Cards seen (entry)")
        cardbox.pack(fill="x", padx=8, pady=(0,6))
        for i,r in enumerate(CARD_ORDER):
            ttk.Button(cardbox, text=DISPLAY[r], width=4, command=lambda rr=r: self.add_card(rr)).grid(row=0, column=i, padx=2, pady=4)
        ttk.Button(cardbox, text="Undo", command=self.undo).grid(row=0, column=len(CARD_ORDER), padx=(12,4))
        ttk.Button(cardbox, text="Reset shoe", command=self.reset_shoe).grid(row=0, column=len(CARD_ORDER)+1, padx=4)

    def _build_table(self):
        box = ttk.LabelFrame(self.page, text="Counts & EV (approx)")
        box.pack(fill="x", padx=8, pady=6)
        cols = ("System","RC","TC (trunc)","TC (floor)","TC (float)","EV % (≈)","Insurance ROI")
        tree = ttk.Treeview(box, columns=cols, show="headings", height=6)
        for c in cols: tree.heading(c, text=c); tree.column(c, anchor="center", width=120)
        tree.pack(fill="x", padx=6, pady=4)
        self.tree = tree
        self.rows = {name: tree.insert("", "end", values=(name,"—","—","—","—","—","—")) for name,_ in SYSTEMS}

    def _build_mid_notebook(self):
        nb = ttk.Notebook(self.page)
        nb.pack(fill="x", padx=8, pady=6)

        tab1 = ttk.Frame(nb); nb.add(tab1, text="Counting / Inputs")
        tab2 = ttk.Frame(nb); nb.add(tab2, text="Advisor / Compare")

        # ---- Tab1: per-rank counts + shoe progress
        self.progress_var = tk.StringVar(value="Shoe progress: —")
        ttk.Label(tab1, textvariable=self.progress_var).grid(row=0, column=0, columnspan=15, sticky="w", padx=6, pady=(6,4))

        cols1 = ("Type","2","3","4","5","6","7","8","9","10","J","Q","K","A")
        self.tab1_tree = ttk.Treeview(tab1, columns=cols1, show="headings", height=2)
        for c in cols1:
            self.tab1_tree.heading(c, text=c)
            self.tab1_tree.column(c, anchor="center", width=52 if c!="Type" else 80)
        self.tab1_tree.grid(row=1, column=0, columnspan=15, padx=6, pady=(0,8), sticky="we")
        self.tab1_rows = {
            "Seen": self.tab1_tree.insert("", "end", values=("Seen",) + tuple("0" for _ in CARD_ORDER)),
            "Remaining": self.tab1_tree.insert("", "end", values=("Remaining",) + tuple("0" for _ in CARD_ORDER)),
        }

        # Small action bar for quick corrections
        bar = ttk.Frame(tab1); bar.grid(row=2, column=0, columnspan=15, sticky="w", padx=6, pady=(0,6))
        ttk.Button(bar, text="Undo", command=self.undo).pack(side="left", padx=(0,6))
        ttk.Button(bar, text="Reset shoe", command=self.reset_shoe).pack(side="left")        

        # Advisor
        row=0
        ttk.Label(tab2, text="Player hand (e.g., 10 6 / A 7 / 8 8):").grid(row=row, column=0, sticky="w", padx=6)
        self.hand_entry = ttk.Entry(tab2, width=18); self.hand_entry.grid(row=row, column=1, sticky="w")
        self.hand_entry.bind("<Return>", lambda e: self.advise_btn())  # UX: Enter => advisor
        ttk.Label(tab2, text="Dealer upcard:").grid(row=row, column=2, sticky="e", padx=4)
        self.upvar = tk.StringVar(value='10')
        up_opts = [DISPLAY[r] for r in CARD_ORDER]
        self.upcombo = ttk.Combobox(tab2, textvariable=self.upvar, values=up_opts, width=6, state="readonly"); self.upcombo.grid(row=row, column=3, sticky="w")
        ttk.Button(tab2, text="Advisor", command=self.advise_btn).grid(row=row, column=4, padx=6)
        ttk.Button(tab2, text="Compare (simulate)", command=self.compare_btn).grid(row=row, column=5, padx=6)
        row+=1
        self.advice_base = tk.StringVar(value="Action (base + indexes): —")
        self.advice_sim  = tk.StringVar(value="EV comparison (%): —")
        ttk.Label(tab2, textvariable=self.advice_base, foreground="#333333").grid(row=row, column=0, columnspan=6, sticky="w", padx=6, pady=2); row+=1
        ttk.Label(tab2, textvariable=self.advice_sim,  foreground="#333333").grid(row=row, column=0, columnspan=6, sticky="w", padx=6, pady=2)

    def _build_ev_panel(self):
        box = ttk.LabelFrame(self.page, text="Advanced EV")
        box.pack(fill="x", padx=8, pady=6)
        ttk.Checkbutton(box, text="Apply indices (Ill18+Fab4)", variable=self.apply_idx_var).grid(row=0, column=0, padx=6, sticky="w")
        ttk.Label(box, text="# hands (EV sim)").grid(row=0, column=1, padx=6, sticky="e")
        ttk.Spinbox(box, from_=2000, to=1000000, textvariable=self.hands_var, width=9, justify="center").grid(row=0, column=2, padx=2, sticky="w")
        ttk.Label(box, text="# hands (EOR calibration)").grid(row=0, column=3, padx=6, sticky="e")
        ttk.Spinbox(box, from_=2000, to=200000, textvariable=self.hands_eor_var, width=9, justify="center").grid(row=0, column=4, padx=2, sticky="w")
        ttk.Button(box, text="Simulate EV", command=self.simulate_ev_btn).grid(row=0, column=5, padx=8)
        ttk.Button(box, text="Calibrate EOR", command=self.calibrate_eor_btn).grid(row=0, column=6, padx=8)
        ttk.Button(box, text="Apply EOR", command=self.ev_eor_btn).grid(row=0, column=7, padx=8)
        self.ev_sim_var = tk.StringVar(value="Simulated EV: —")
        self.kelly_var  = tk.StringVar(value="Kelly (≈): —")
        self.eor_status = tk.StringVar(value="EOR: —")
        ttk.Label(box, textvariable=self.ev_sim_var).grid(row=1, column=0, columnspan=3, sticky="w", padx=6, pady=(6,0))
        ttk.Label(box, textvariable=self.kelly_var).grid(row=1, column=3, columnspan=2, sticky="w", padx=6, pady=(6,0))
        ttk.Label(box, textvariable=self.eor_status).grid(row=1, column=5, columnspan=2, sticky="w", padx=6, pady=(6,0))

    def _build_status(self):
        box = ttk.LabelFrame(self.page, text="Status / tools")
        box.pack(fill="x", padx=8, pady=6)
        ttk.Button(box, text="+1 card 10", command=lambda: self.add_card('T')).grid(row=0, column=0, padx=4, pady=4)
        ttk.Button(box, text="+1 card A",  command=lambda: self.add_card('A')).grid(row=0, column=1, padx=4, pady=4)
        ttk.Button(box, text="Reset", command=self.reset_shoe).grid(row=0, column=2, padx=4, pady=4)

    # ---- rules / shoe logic ----
    def _sync_peek_enhc(self):
        if self.enhc_var.get():
            self.peek_var.set(False)
        elif self.peek_var.get():
            self.enhc_var.set(False)
        self.update_all()

    def decks_total_cards(self):
        return int(self.decks_var.get())*52

    def decks_remaining(self):
        # TC denominator = cards remaining UP TO THE CUT (penetration), not the whole shoe.
        seen = sum(self.cards_seen[r] for r in CARD_ORDER)
        total = self.decks_total_cards()
        cut = int(total*(self.pen_var.get()/100.0))  # number of cards dealt before reshuffle
        seen_to_cut = min(seen, cut)
        remain_to_cut = max(0, cut - seen_to_cut)
        decks = remain_to_cut/52.0
        return max(MIN_DECKS_DEN, decks)

    def shoe_progress(self):
        total = self.decks_total_cards()
        cut = int(total*(self.pen_var.get()/100.0))
        seen = sum(self.cards_seen[r] for r in CARD_ORDER)
        seen_to_cut = min(seen, cut)
        remain_to_cut = max(0, cut - seen_to_cut)
        return seen_to_cut, cut, total, remain_to_cut

    def remaining_counts(self):
        total = self.decks_total_cards()
        base = {r:(total//13) for r in CARD_ORDER}
        # 52*D is always divisible by 13 -> no remainder, but keep generic code
        for r in CARD_ORDER: base[r] += 1 if CARD_ORDER.index(r) < (total % 13) else 0
        for r in CARD_ORDER: base[r] -= self.cards_seen[r]
        return {r:max(0, base[r]) for r in CARD_ORDER}

    # ---- counting ----
    def add_card(self, r):
        if r not in CARD_ORDER: return
        rem = self.remaining_counts()
        if sum(rem.values()) <= 0: return
        if rem.get(r, 0) <= 0:
            try: self.root.bell()
            except Exception: pass
            return
        self.cards_seen[r] += 1
        self.history.append(r)
        self.update_all()

    def undo(self):
        if not self.history: return
        r = self.history.pop()
        self.cards_seen[r] = max(0, self.cards_seen[r]-1)
        self.update_all()

    def reset_shoe(self):
        self.cards_seen = {r:0 for r in CARD_ORDER}
        self.history = []
        self.update_all()

    def compute_running(self, system_map):
        rc = 0
        for r in CARD_ORDER:
            rc += system_map.get(r,0)*self.cards_seen[r]
        return rc

    def tc_values(self, system_name, system_map):
        rc = self.compute_running(system_map)
        rem_decks = self.decks_remaining()
        tc_float = rc / rem_decks if rem_decks>0 else 0.0
        tc_floor = math.floor(tc_float)
        tc_trunc = math.trunc(tc_float)  # truncated (betting)
        return rc, tc_float, tc_floor, tc_trunc

    def insurance_ev_comp(self):
        rem = self.remaining_counts()
        denom = sum(rem[r] for r in CARD_ORDER)
        if denom<=0: return None
        tens = rem['T']+rem['J']+rem['Q']+rem['K']
        p = tens/denom
        # Insurance ROI (2:1): EV = 2p - 1 → in %
        return (2.0*p - 1.0)*100.0

    
    def update_all(self):
        base_edge = estimate_base_edge(self.decks_var.get(), self.h17_var.get(), self.das_var.get(),
                                       self.rsa_var.get(), self.hsa_var.get(), self.dos_var.get(),
                                       self.d10_var.get(), self.ls_var.get(), (self.peek_var.get() and not self.enhc_var.get()))
        rem_decks = self.decks_remaining()

        rc_hilo = self.compute_running(HI_LO)
        tc_hilo = rc_hilo / rem_decks if rem_decks>0 else 0.0
        tc_hilo_floor = math.floor(tc_hilo)

        ins_ev = self.insurance_ev_comp()
        ins_text = f"{ins_ev:+.2f}%" if ins_ev is not None else "—"

        # --- EOR adjustment (composition-sensitive EV correction) ---
        eor_delta = 0.0
        if (getattr(self, "eor_vec", None) is not None and
            getattr(self, "eor_ref_counts", None) is not None and
            getattr(self, "eor_base_ev", None) is not None):
            cur = self.remaining_counts()
            ref = self.eor_ref_counts
            # eor_vec[r]: ΔEV (percentage points) when REMOVING 1 card r from the reference shoe
            eor_delta = sum(self.eor_vec.get(r, 0.0) * (ref.get(r, 0) - cur.get(r, 0)) for r in CARD_ORDER)

        # Main table
        for name, sys_map in SYSTEMS:
            rc, tc_float, tc_floor, tc_trunc = self.tc_values(name, sys_map)
            slope = slope_for(name, self.decks_var.get(), side_ace_used=(self.asc_var.get() if name in ("Omega II","Hi-Opt II") else True))
            # Count-based EV + correction compositionnelle (EOR)
            ev = base_edge + slope * tc_floor + eor_delta
            self.tree.item(self.rows[name], values=(
                name, f"{rc:+d}", f"{tc_trunc:+d}", f"{tc_floor:+d}", f"{tc_float:+.2f}", f"{ev:+.2f}", ins_text
            ))

        # Tab1: visible count + shoe progress
        try:
            if hasattr(self, "tab1_tree"):
                rem = self.remaining_counts()
                seen_vals = ("Seen",) + tuple(str(self.cards_seen[r]) for r in CARD_ORDER)
                rem_vals  = ("Remaining",) + tuple(str(rem[r]) for r in CARD_ORDER)
                self.tab1_tree.item(self.tab1_rows["Seen"], values=seen_vals)
                self.tab1_tree.item(self.tab1_rows["Remaining"], values=rem_vals)

            if hasattr(self, "progress_var"):
                seen_to_cut, cut_cards, total_cards, remain_to_cut = self.shoe_progress()
                seen_total = sum(self.cards_seen[r] for r in CARD_ORDER)
                self.progress_var.set(
                    f"Shoe progress: seen {seen_total}/{total_cards}  |  seen up to cut {seen_to_cut}/{cut_cards}  (remaining up to cut: {remain_to_cut})"
                )
        except Exception as _e:
            # do not block the app if the tab isn't built yet
            pass


    # ---- Advanced EV (UI-safe threads) ----
    def simulate_ev_btn(self):
        rules=self.current_rules()
        rem=self.remaining_counts()
        if sum(rem.values())<20:
            messagebox.showerror("Simulation","Not enough cards.")
            return
        hands=max(2000,int(self.hands_var.get()))
        tc_floor = math.floor(self.compute_running(HI_LO)/self.decks_remaining())
        apply_idx = bool(self.apply_idx_var.get())
        self.ev_sim_var.set("Simulated EV: in progress…")
        self.kelly_var.set("Kelly (≈): …")
        def work():
            mean,var = simulate_ev(rem, rules, hands=hands, seed=random.randrange(1,10_000_000), tc_floor=tc_floor, apply_idx=apply_idx)
            edge_units = mean/100.0
            kelly = max(0.0, min(1.0, edge_units/var)) if var>0 else 0.0
            def ui():
                self.ev_sim_var.set(f"Simulated EV: {mean:+.2f}%  (var≈{var:.3f}, hands={hands}, idx={'ON' if apply_idx else 'OFF'})")
                self.kelly_var.set(f"Kelly (≈): {kelly*100:.1f}% of unit bankroll")
            self.root.after(0, ui)
        threading.Thread(target=work, daemon=True).start()

    def calibrate_eor_btn(self):
        rules=self.current_rules()
        rem=self.remaining_counts()
        if sum(rem.values())<20:
            messagebox.showerror("EOR","Not enough cards.")
            return
        hands=max(6000,int(self.hands_eor_var.get()))
        tc_floor = math.floor(self.compute_running(HI_LO)/self.decks_remaining())
        apply_idx = bool(self.apply_idx_var.get())
        self.eor_status.set("EOR: calibrating…")
        def work():
            base,eor = calibrate_eor(rem, rules, hands=hands, seed=random.randrange(1,10_000_000), tc_floor=tc_floor, apply_idx=apply_idx)
            def ui():
                self.eor_base_ev = base; self.eor_vec = eor; self.eor_ref_counts = rem
                self.eor_status.set(f"EOR: calibrated (EV0={base:+.2f}%)")
                self.update_all()
            self.root.after(0, ui)
        threading.Thread(target=work, daemon=True).start()

    def ev_eor_btn(self):
        if self.eor_vec is None or self.eor_base_ev is None or self.eor_ref_counts is None:
            messagebox.showwarning("EOR", "Calibrate EOR first."); return
        self.update_all()

    def current_rules(self):
        return {
            "H17": self.h17_var.get(),
            "DAS": self.das_var.get(),
            "RSA": self.rsa_var.get(),
            "HSA": self.hsa_var.get(),
            "DOUBLE_ON_SPLIT_ACES": self.dos_var.get(),
            "D10": self.d10_var.get(),
            "PEEK": (self.peek_var.get() and not self.enhc_var.get()),
            "OBO": self.obo_var.get(),
            "BJ_3_2": self.bj32_var.get(),
            "LS": self.ls_var.get(),
        }

    # ---- Advisor / Compare ----
    def advise_btn(self):
        hand_txt = getattr(self, "hand_entry").get().strip()
        ranks = parse_hand_text(hand_txt)
        if len(ranks)!=2:
            messagebox.showwarning("Invalid hand", "Enter exactly 2 cards (ex: '10 6', 'A 7', '8 8')."); return
        inv = {v:k for k,v in DISPLAY.items()}
        up = inv.get(self.upvar.get(), 'T')

        rules=self.current_rules()
        rc_hilo = self.compute_running(HI_LO); tc_floor = math.floor( rc_hilo / self.decks_remaining() )

        tot, soft = hand_total(ranks)
        pair = (('T' if ranks[0] in TEN_RANKS else ranks[0]) == ('T' if ranks[1] in TEN_RANKS else ranks[1]))
        action = None
        if pair and should_split('T' if ranks[0] in TEN_RANKS else ranks[0], up, rules):
            action = 'Split'
        else:
            override = apply_indices_override(tot, soft, up, True, True, tc_floor, rules) if self.apply_idx_var.get() else None
            if override == 'D': action = 'Double'
            elif override == 'S': action = 'Stand'
            elif override == 'H': action = 'Hit'
            elif override == 'SUR': action = 'Surrender'
            else: action = {'H':'Hit','S':'Stand','D':'Double'}.get(soft_action(tot, up, rules, True) if soft else hard_action(tot, up, rules, True), 'Hit')

        # Base surrender if no index forces another action (and not 8,8)
        first_two = (len(ranks) == 2)
        if action in ('Hit','Stand','Double') and self.ls_var.get() and first_two and not soft and not (ranks[0]=='8' and ranks[1]=='8'):
            if (tot == 16 and up in ('9','T','J','Q','K','A')) or (tot == 15 and up == 'T'):
                action = 'Surrender'
        self.advice_base.set(f"Action (base + indices): {action}  |  (TC Hi-Lo={tc_floor:+d})")

    def compare_btn(self):
        hand_txt = getattr(self, "hand_entry").get().strip()
        ranks = parse_hand_text(hand_txt)
        if len(ranks)!=2:
            messagebox.showwarning("Invalid hand", "Enter exactly 2 cards (ex: '10 6', 'A 7', '8 8')."); return
        inv = {v:k for k,v in DISPLAY.items()}
        up = inv.get(self.upvar.get(), 'T')
        rules=self.current_rules(); rem=self.remaining_counts()
        hands= max(4000, int(self.hands_var.get())//4)
        tc_floor = math.floor( self.compute_running(HI_LO) / self.decks_remaining() )
        apply_idx = bool(self.apply_idx_var.get())

        actions = ['STAND','HIT','DOUBLE']
        if (('T' if ranks[0] in TEN_RANKS else ranks[0]) == ('T' if ranks[1] in TEN_RANKS else ranks[1])): actions.append('SPLIT')
        if rules["LS"] and not (ranks[0]=='8' and ranks[1]=='8'): actions.append('SURRENDER')

        results = {}
        for a in actions:
            ev = simulate_fixed_action(rem, rules, ranks, up, hands=hands, seed=random.randrange(1,10_000_000),
                                       tc_floor=tc_floor, apply_idx=apply_idx, force=a)
            results[a]=ev

        best = max(results, key=lambda k: results[k])
        parts = [f"{a}: {results[a]:+5.2f}%" for a in ['STAND','HIT','DOUBLE','SPLIT','SURRENDER'] if a in results]
        self.advice_sim.set(f"EV comparison (%):  " + "   |   ".join(parts) + f"   →  Recommended: {best}")

# ---- parsing main text ----
def parse_hand_text(s):
    s = s.replace(',', ' ').replace('/', ' ').replace('+', ' ').strip()
    toks = [t for t in s.split() if t]
    if len(toks)!=2: return []
    def tok_to_rank(t):
        t=t.upper()
        if t in ('10','T'): return 'T'
        if t in ('J','Q','K','A'): return t
        if t in ('2','3','4','5','6','7','8','9'): return t
        return 'T'
    return [tok_to_rank(toks[0]), tok_to_rank(toks[1])]

# ---- Launch ----
def main():
    root = tk.Tk()
    try:
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")
    except Exception:
        pass
    # No minsize: keep the window small and scroll
    root.geometry("980x620")
    app = ProApp(root)
    root.mainloop()

if __name__=="__main__":
    main()