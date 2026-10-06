"""make_quests.py -- writes quests.json for the 3D hub: the quest registry (main + side quests) and the NPC marks.

    python make_quests.py

quests.json = {"quests": [...], "marks": {...}}
  quest: id, kind ("main"|"side"), title, giver, where, summary,
         accept   flag set when the quest is taken (it appears in the log)
         ready    flag spec: the objective is done, go back to the giver (status "ready")
         done     flag that completes it
         steps    [{if, unless, text, count:[flag,...]}]  first match = the current objective
  marks: "scene/npcId" -> "main!" | "main?" | "side!" | "side?" | "later" (a quest not open yet), or a list of
         {if, unless, mark} (first match wins). Anything not listed gets an automatic mark in hub3d.js from what the NPC does
         (shop, heroes, summon, battle, ladder, travel, rest, dice, foe/elite/boss fights).
Quest marks live here, not in the scene files, so re-saving a scene in the 3D builder cannot lose them.
"""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))


def Q(id, kind, title, giver, where, summary, accept, done, steps, ready=None):
    q = dict(id=id, kind=kind, title=title, giver=giver, where=where, summary=summary, accept=accept, done=done, steps=steps)
    if ready:
        q["ready"] = ready
    return q


def S(text, if_=None, unless=None, count=None):
    s = {"text": text}
    if if_: s["if"] = if_
    if unless: s["unless"] = unless
    if count: s["count"] = count
    return s


MAIN = [
    Q("m_wood", "main", "The Thorn Barrier", "Mayor Orrin", "Paradise Island",
      "Thorns choke the Whispering Wood and the goblins feed them. Find Ranger Willa and reach the Old Oak Grove.",
      "fq_start", "fq_done", ready="fq_seal", steps=[
          S("Find Ranger Willa in the Whispering Wood (the path in the north-west). Follow the water and find who feeds the thorn barrier.", "fq_start", "fq_chief"),
          S("Cut through the withered brambles and reach the Old Oak Grove.", "fq_chief", "fq_boss"),
          S("Speak with Ranger Willa in the grove.", "fq_boss", "fq_seal"),
          S("Bring the Warden's Seal to Mayor Orrin.", "fq_seal", "fq_done")]),
    Q("m_lani", "main", "Escort Through the Hollow Cave", "Elder Mahina", "Hollow Cave, north of the village",
      "Elder Mahina asked you to see a chapel healer, Sera, through the Hollow Cave and out to the Colosseum.",
      "st_quest", "st_done", steps=[
          S("Meet Sera at the arch of the Hollow Cave, north of the village.", "st_quest", "st_sera"),
          S("Escort Sera through the Hollow Cave. Light the lamps, raise the causeway and open the Sovereign's door.", "st_sera", "dg_guards"),
          S("Help the Colosseum guards: the Drowned Sovereign is tearing them apart.", "dg_guards", "st_done")]),
    Q("m_pit", "main", "Slave of the Colosseum", "", "The Pit",
      "You are in the Colosseum's pit. Win fights for the Overseer and climb the ladder to earn your freedom.",
      "st_jailed", "st_free", steps=[S("Fight for the Overseer until you rise past the freedom rank and win your release.", "st_jailed", "st_free")]),
    Q("m_sera", "main", "The Infirmary", "", "Olympus Colosseum",
      "Sera was taken to the Colosseum infirmary while Kael was thrown in the Pit.", "st_hurt", "st_sera_back", steps=[
          S("Win your freedom in the Pit, then find Sera.", "st_hurt", "st_free"),
          S("Find Sera in the Colosseum infirmary, on the west side of the concourse.", "st_free", "st_sera_back")]),
    Q("m_home", "main", "The Way Home", "", "Olympus Colosseum",
      "You are free. Leave through the main gate and take the ferry home.", "st_free", "st_siege",
      [S("You are free! Leave through the main gate and take the ferry home to Paradise Island.", "st_free", "st_siege")]),
    Q("m_siege", "main", "Defend the Colosseum", "", "Olympus Colosseum",
      "Raiders have stormed the Colosseum gate.", "st_siege", "st_space",
      [S("Defend the Colosseum!", "st_siege", "st_space")]),
    Q("m_kestrel", "main", "Outpost Kestrel", "Captain Rhea", "Outpost Kestrel",
      "You came through the rift. Captain Rhea and a rift scholar named Lyra want to talk to you.",
      "st_landed", "st_lyra", steps=[
          S("Speak with Captain Rhea.", "st_landed", "st_met"),
          S("Find Lyra, the rift scholar Captain Rhea told you about (the mess hall, west of the pad).", "st_met", "st_lyra")]),
    Q("m_vault", "main", "The Shard Vault", "Lyra", "Beneath Outpost Kestrel",
      "Lyra's compass points beneath the base. Clear the Shard Vault and defeat the Vault Warden.",
      "st_lyra", "vt_boss", steps=[
          S("Take the hatch west of the landing pad and clear the Shard Vault. Fight through the floating maze (west walkway first) and defeat the Vault Sentinel.", "st_lyra", "vt_g1"),
          S("The east gate is open. Reach the Phase Stalker at the end of the east maze.", "vt_g1", "vt_g2"),
          S("Cross the north walkways and defeat the Rift Colossus. The Warden's core lies beyond.", "vt_g2", "vt_g3"),
          S("The north sector is cleared. The sealed door to the Warden's core is open.", "vt_g3", "vt_boss")]),
    Q("m_reach", "main", "The Shattered Reach", "Captain Rhea", "Outpost Kestrel, then the Reach",
      "A new coordinate has resolved on the rift console.", "vt_boss", "rc_end", steps=[
          S("A new coordinate has resolved on the rift console. Step into the rift gate east of the landing pad.", "vt_boss", "rc_arrive"),
          S("Fight across the floating ruins and defeat the Breach Warden to open the gate to the second court.", "rc_arrive", "rc_g1"),
          S("Cross the bridge and defeat the Rift Harbinger in its arena.", "rc_g1", "rc_boss"),
          S("The Harbinger has fallen. Step through the rift gate back to Outpost Kestrel.", "rc_boss", "rc_end")]),
]

SIDE = [
    Q("s_net", "side", "Pua's Lost Net", "Pua", "Paradise Island pier",
      "A storm swept Pua's best net up the stream into the Whispering Wood.", "sq_net_q", "sq_net_done", ready="sq_net", steps=[
          S("Pua (island pier): find his lost fishing net in the Whispering Wood.", "sq_net_q", "sq_net"),
          S("Pua: bring the net back.", "sq_net", "sq_net_done")]),
    Q("s_fence", "side", "The Goblin Brute", "Old Tane", "Paradise Island farm",
      "A goblin brute smashes Old Tane's fence every night.", "sq_fence_q", "sq_fence_done", ready="sq_fence", steps=[
          S("Old Tane (island farm): beat the goblin brute by his fence.", "sq_fence_q", "sq_fence"),
          S("Old Tane: collect your reward.", "sq_fence", "sq_fence_done")]),
    Q("s_pages", "side", "Torn Glyph Pages", "Scholar Nema", "Paradise Island",
      "Three torn pages of Nema's moon-glyph survey are scattered: one near the cave path, two in the Whispering Wood.",
      "sq_pg_q", "sq_pg_done", ready="sq_pg1,sq_pg2,sq_pg3", steps=[
          S("Scholar Nema (island): find the torn glyph pages (cave path, Whispering Wood).", "sq_pg_q", "sq_pg_done", ["sq_pg1", "sq_pg2", "sq_pg3"])]),
    Q("s_spring", "side", "The Spirit Spring", "Mossbeard", "Whispering Wood",
      "Mossbeard asks you to drink from the spirit spring and listen.", "sq_moss_q", "sq_moss_done", ready="sq_spring", steps=[
          S("Mossbeard (Whispering Wood): drink from the spirit spring.", "sq_moss_q", "sq_spring"),
          S("Mossbeard: tell him what you heard.", "sq_spring", "sq_moss_done")]),
    Q("s_locket", "side", "The Silver Locket", "Mara", "Colosseum town",
      "Mara lost a silver locket with a blue stone on the harbour road.", "sq_locket_q", "sq_locket_done", ready="sq_locket", steps=[
          S("Mara (Colosseum town): find her locket on the harbour road.", "sq_locket_q", "sq_locket"),
          S("Mara: return the locket.", "sq_locket", "sq_locket_done")]),
    Q("s_knight", "side", "The Runaway Knight", "Pip", "Colosseum town",
      "Pip wants the runaway knight on the road dealt with.", "sq_bounty_q", "sq_bounty_done", ready="sq_bounty", steps=[
          S("Pip (Colosseum town): defeat the runaway knight on the road.", "sq_bounty_q", "sq_bounty"),
          S("Pip: collect your reward.", "sq_bounty", "sq_bounty_done")]),
    Q("s_salvage", "side", "Loose Salvage", "Scrapper Vel", "Outpost Kestrel",
      "Three salvage crates have gone astray around the outpost.", "sq_salv_q", "sq_salv_done", ready="sq_s1,sq_s2,sq_s3", steps=[
          S("Scrapper Vel (Outpost Kestrel): recover the loose salvage crates.", "sq_salv_q", "sq_salv_done", ["sq_s1", "sq_s2", "sq_s3"])]),
    Q("s_drone", "side", "The Rogue Drone", "Corporal Dun", "Outpost Kestrel",
      "A drone has gone rogue past the east scaffolding.", "sq_drone_q", "sq_drone_done", ready="sq_drone", steps=[
          S("Corporal Dun (Outpost Kestrel): shut down the rogue drone past the east scaffolding.", "sq_drone_q", "sq_drone"),
          S("Corporal Dun: collect the reserve.", "sq_drone", "sq_drone_done")]),
]

MARKS = {
    "island/mayor0": "main!", "island/mayor2": "main?",
    "island/elder": "later", "island/elder1": "main!",
    "island/sera_arch": [{"if": "st_quest", "unless": "st_sera", "mark": "main!"}],
    "olympus/sera_infirmary": [{"if": "st_free,st_hurt", "unless": "st_sera_back", "mark": "main!"}],
    "forest/willa1": "main?",
    "asteroid/rhea": [{"unless": "st_met", "mark": "main!"}],
    "asteroid/lyra": [{"if": "st_met", "mark": "main?"}],
    "island/sq_pua0": "side!", "island/sq_pua2": "side?",
    "island/sq_tane0": "side!", "island/sq_tane2": "side?",
    "island/sq_nema0": "side!", "island/sq_nema1": [{"if": "sq_pg1,sq_pg2,sq_pg3", "mark": "side?"}],
    "forest/sq_moss0": "side!", "forest/sq_moss2": "side?",
    "outside/sq_mara0": "side!", "outside/sq_mara2": "side?",
    "outside/sq_pip0": "side!", "outside/sq_pip2": "side?",
    "asteroid/sq_vel0": "side!", "asteroid/sq_vel1": [{"if": "sq_s1,sq_s2,sq_s3", "mark": "side?"}],
    "asteroid/sq_kade0": "side!", "asteroid/sq_kade2": "side?",
    "island/ferry": "travel",
}

if __name__ == "__main__":
    out = {"quests": MAIN + SIDE, "marks": MARKS}
    with open(os.path.join(HERE, "quests.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("quests.json:", len(out["quests"]), "quests,", len(MARKS), "marks")
