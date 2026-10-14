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
      "Elder Mahina asked you to see a chapel healer, Miya, through the Hollow Cave and out to the Colosseum.",
      "st_quest", "st_done", steps=[
          S("Meet Miya at the arch of the Hollow Cave, north of the village.", "st_quest", "st_sera"),
          S("Escort Miya through the Hollow Cave. Light the lamps, raise the causeway and open the Sovereign's door.", "st_sera", "dg_guards"),
          S("Help the Colosseum guards: the Drowned Sovereign is tearing them apart.", "dg_guards", "st_done")]),
    Q("m_pit", "main", "Slave of the Colosseum", "", "The Pit",
      "You are in the Colosseum's pit. Win fights for the Overseer and climb the ladder. The crowd wants to buy your collar.",
      "st_jailed", "st_free", steps=[
          S("Fight for the Overseer until you rise past the freedom rank.", "st_jailed", "st_ceremony"),
          S("The releasing ceremony is at dawn. Rest on your cot in your cell to pass the night.", "st_ceremony", "st_night"),
          S("Someone is coming for you in the dark.", "st_night", "st_free")]),
    Q("m_sera", "main", "Find Miya", "", "Outpost Kestrel",
      "Captain Varro said Miya was taken to the Colosseum infirmary. Rook says she never was.", "st_hurt", "st_sera_back", steps=[
          S("Win your way out of the Pit, then find Miya.", "st_hurt", "st_space"),
          S("Find Miya. She is waiting for you at the edge of the landing pad.", "st_space", "st_sera_back")]),
    Q("m_kestrel", "main", "Outpost Kestrel", "Captain Rhea", "Outpost Kestrel",
      "You came through the rift. Captain Rhea and a rift scholar named Lyra want to talk to you.",
      "st_landed", "st_lyra", steps=[
          S("Reunite with Miya, then hear Rook out. He is near the landing pad.", "st_landed", "st_rook_told"),
          S("Rook says the answers are in the Vault. Speak with Captain Rhea first.", "st_rook_told", "st_met"),
          S("Find Lyra, the rift scholar Captain Rhea told you about (the mess hall, west of the pad).", "st_met", "st_lyra")]),
    Q("m_vault", "main", "The Shard Vault", "Lyra", "Beneath Outpost Kestrel",
      "Lyra's compass points beneath the base. Clear the Shard Vault and defeat the Vault Warden.",
      "st_lyra", "vt_boss", steps=[
          S("Take the hatch west of the landing pad and clear the Shard Vault. Fight through the floating maze (west walkway first) and defeat the Vault Sentinel.", "st_lyra", "vt_g1"),
          S("The east gate is open. Reach the Phase Stalker at the end of the east maze.", "vt_g1", "vt_g2"),
          S("Cross the north walkways and defeat the Rift Colossus. The Warden's core lies beyond.", "vt_g2", "vt_g3"),
          S("The north sector is cleared. The sealed door to the Warden's core is open.", "vt_g3", "vt_boss")]),
    Q("m_reach", "main", "The Shattered Reach", "Captain Rhea", "Outpost Kestrel, then the Reach",
      "A new coordinate has resolved on the rift console.", "rc_arrive", "rc_end", steps=[
          S("A new coordinate has resolved on the rift console. Step into the rift gate east of the landing pad.", "vt_boss", "rc_arrive"),
          S("Fight across the floating ruins and defeat the Breach Warden to open the gate to the second court.", "rc_arrive", "rc_g1"),
          S("Cross the bridge and defeat the Rift Harbinger in its arena.", "rc_g1", "rc_boss"),
          S("The Harbinger has fallen. Step through the rift gate back to Outpost Kestrel.", "rc_boss", "rc_end")]),
    Q("m_mind", "main", "The Door in the Vault", "Rook", "The Shard Vault",
      "Rook says the sealed door at the heart of the Vault has never opened for anyone. He wants to see what it does for you.",
      "vt_boss", "st_mind", steps=[
          S("The Warden has fallen. Rook is waiting at the end of the arena.", "vt_boss", "st_mind_a"),
          S("The door has opened.", "st_mind_a", "st_mind")]),
    Q("m_strange", "main", "Rebuild Dawnwatch", "Brannoch", "Dawnwatch Keep",
      "The Mind has the shard and Kenji's party has fallen into a world with nowhere to go. A mason named Brannoch wants to raise the ruined keep of Dawnwatch again. Find its people, win its fights and pay for its stone.",
      "st_mind", "hp_4", steps=[
          S("Speak with the mason, Brannoch, by the camp.", "st_mind", "hr_mason"),
          S("Phase II, the Camp: find Orla (west rubble) and Tilda (old chapel cellar, east), then pay Brannoch (600 gold, 12 shards).", "hr_mason", "hp_2"),
          S("Phase III, the Village: find Pell (the wagon outside the south gate) and Wick (the east pond), defeat the Hollow Knight at the keep door, then pay Brannoch (1800 gold, 35 shards).", "hp_2", "hp_3"),
          S("Phase IV, the Castle Town: find Sennet (north-east library ruin) and Dove (north-east tower), defeat the Cult Seer outside the north postern, then pay Brannoch (4200 gold, 70 shards).", "hp_3", "hp_4")]),
    Q("m_eldergate", "main", "Under the Ruins", "Brannoch", "Dawnwatch, north-west ruin",
      "Brannoch cannot lift or dig under a humming paved ring in the north-west ruin. Kenji's mark answers it. Dawnwatch's real name is Eldergate, and a buried network of gates lies beneath it.",
      "hr_mason", "eg_veyra_go", steps=[
          S("Lay your hand on the humming ring stone in Dawnwatch's north-west ruin.", "hr_mason", "eg_open"),
          S("Beneath the ruins, read the Chronicle plates (hall and east alcove) and the Watcher's Ledger (west alcove), then touch the Core.", "eg_open", "eg_core", ["eg_t1", "eg_t2", "eg_t3", "eg_t4", "eg_t5", "eg_ledger"]),
          S("Step through the open Veyra gate (third from the east along the north wall).", "eg_core", "eg_veyra_go")]),
    Q("m_veyra", "main", "Veyra, the Kingdom of Ash", "Reya", "Cinder Hollow, Veyra",
      "Veyra is a kingdom burning its own hearth to keep warm. In the outer village of Cinder Hollow, a courier named Reya guards the last of the medicine. The royal garrison took the rest.",
      "eg_veyra_go", "vy_join", steps=[
          S("Recover Cinder Hollow's confiscated medicine from the royal garrison on the north road.", "eg_veyra_go", "vy_supplies"),
          S("Take the medicine to Marta in the sick house, west of the well.", "vy_supplies", "vy_join")]),
    Q("m_ashroad", "main", "The Road of Ash", "Reya", "North of Cinder Hollow, Veyra",
      "Reya's brother Tomas was sent to the capital, Solgard, six years ago. The only road there runs north through the abandoned provinces. Somewhere along it, the Crown has hung its hunger on a hill.",
      "vy_join", "ar_end", steps=[
          S("Take the Road of Ash north, past the garrison. Old Maud keeps a fire at the Wayfarers' Rest.", "vy_join", "ar_arrive"),
          S("Reach Harrow's Ford, three days up the road, and the Tithe Spire that is freezing it. Defeat the Spire Warden.", "ar_arrive", "ar_warden"),
          S("Decide what to do with the Tithe Spire. You can sever it, or leave it humming.", "ar_warden", "ar_spire_done"),
          S("Walk on to the old toll bridge. Quartermaster Hesk holds it for the Cold Gate.", "ar_spire_done", "ar_hesk"),
          S("Find the Underdrain hatch behind the east pier and knock three, then two.", "ar_hesk", "ar_end")]),
    Q("m_solgard", "main", "Solgard, the Sunwall City", "Reya", "Solgard, Veyra",
      "Under the Sunwall is Veyra's last city, warm and kind and fed by something it does not look at. Reya's brother Tomas is in the Works, where the kindlers are kept.",
      "ar_end", "sg_end", steps=[
          S("Speak with the lamplighter, Odo, at the foot of the Underdrain.", "ar_end", "sg_odo"),
          S("Climb the drain stair and enter the Bright Ring. Mind the gold mark on your right hand.", "sg_odo", "sg_speech"),
          S("The Works lies east of the palace. Get past Overseer Cathal at its gate.", "sg_speech", "sg_overseer"),
          S("Cross the Works to the Great Valve and find Tomas.", "sg_overseer", "sg_tomas"),
          S("Decide how to answer Tomas.", "sg_tomas", "sg_tomas2"),
          S("Take the kindler's key to the Great Valve and go down to the Emberheart.", "sg_tomas2", "sg_end")]),
    Q("m_heart", "main", "The Heart beneath the Throne", "Reya", "Beneath the palace, Solgard",
      "Under Solgard's throne the Emberheart beats, the last of an old god's warmth, and every child in the Works is piped into it. Queen Maelis waits at the bottom, and so does someone who does not want you to see her face.",
      "sg_end", "eh_end", steps=[
          S("Go down the valve stair and defeat Captain Rhenn at the inner gate.", "sg_end", "eh_captain"),
          S("Cross the Gallery of Names and enter the Emberheart chamber.", "eh_captain", "eh_parley"),
          S("Defeat the Ember Regent that guards the Heart.", "eh_parley", "eh_regent"),
          S("Reconnect the Emberheart, and decide what becomes of Queen Maelis.", "eh_regent", "eh_end")]),
    Q("m_dawn", "main", "Solgard, Dawn", "Reya", "The Palace Square, Solgard",
      "The Emberheart burns for itself, the Sunwall is out, and the sky is back. Reya has a brother to say goodbye to, and the counsellor in the crowd has something to say.",
      "eh_end", "dn_end", steps=[
          S("Climb out into the dawn and find Tomas by the fountain.", "eh_end", "dn_tomas"),
          S("Speak to the counsellor who stands apart at the east edge of the square.", "dn_tomas", "dn_watch"),
          S("Step onto the Veyra ring in the south of the square and return to Eldergate.", "dn_watch", "dn_end")]),
    Q("m_hushmere", "main", "A World That Smiles", "Neris", "Hushmere, Lethenia",
      "Lethenia has had no war in three hundred years. Its capital, Hushmere, smiles at strangers and never raises its voice. A junior archivist named Neris has noticed that people go missing without anyone being sad about it.",
      "eg_leth_go", "hs_end", steps=[
          S("Leave the Quiet Garden and talk to the attendant, Sorrel.", "eg_leth_go", "hs_welcome"),
          S("Cross the Avenue to the Concord Square. An archivist wants a word.", "hs_welcome", "hs_neris"),
          S("Speak to the Concordant of Care in the Hall of Concord, east of the square.", "hs_neris", "hs_official"),
          S("Meet Neris at the lower stair, in the west corner of the square.", "hs_official", "hs_end")]),
    Q("m_lowerhush", "main", "The Happiness Protocol", "Neris", "The Lower Districts, Hushmere",
      "Beneath Hushmere's white streets lies the Rest, where citizens who will not stay calm are quietly relocated. Neris has looked for her mentor there eleven times.",
      "hs_end", "lh_end", steps=[
          S("Follow Neris down into the Lower Districts.", "hs_end", "lh_arrive"),
          S("Cross the Quiet Rows to Mender's Row.", "lh_arrive", "lh_woman"),
          S("Find Oriel on the bench by the fountain, and decide what to do for her.", "lh_woman", "lh_choice"),
          S("Open the Sealed Annex and defeat the Correction Warden at its far door.", "lh_choice", "lh_warden"),
          S("Find Archivist Corrow in the Archive Facility.", "lh_warden", "lh_corrow"),
          S("Read the Correction Rolls on his desk.", "lh_corrow", "lh_ledger"),
          S("Leave the facility by the stair at its south end.", "lh_ledger", "lh_end")]),
    Q("m_songhall", "main", "The People Who Chose This", "Neris", "The Hall of Songs, Hushmere",
      "Neris knows people in the old Hall of Songs who have begun to ask questions. They will not agree with each other, or with Kenji.",
      "lh_end", "sh_end", steps=[
          S("Climb to the Hall of Songs and face Tavian.", "lh_end", "sh_arrive"),
          S("Hear Ivel, Hanne, Orsk and Elder Varro argue it out.", "sh_arrive", "sh_debate"),
          S("Take the floor and tell the Hall what you saw.", "sh_debate", "sh_speech"),
          S("Follow Maren Aldwyn through the Old Quarter.", "sh_speech", "sh_walk"),
          S("Read the charter in the sealed vault.", "sh_walk", "sh_charter"),
          S("Give Maren Aldwyn your answer.", "sh_charter", "sh_end")]),
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
    "asteroid/miya_reunion": [{"if": "st_space,st_hurt", "unless": "st_sera_back", "mark": "main!"}],
    "forest/willa1": "main?",
    "asteroid/rhea": [{"unless": "st_met", "mark": "main!"}],
    "asteroid/rook_base": [{"if": "st_sera_back", "unless": "st_rook_told", "mark": "main!"}],
    "vault/vt_rook_end": [{"if": "vt_boss", "unless": "st_mind_a", "mark": "main!"}],
    "strange/brannoch": [{"unless": "hr_mason", "mark": "main!"}, {"unless": "hp_4", "mark": "main?"}],
    "veyra/marta": [{"if": "vy_supplies", "unless": "vy_returned", "mark": "main?"}],
    "veyra/reya": [{"unless": "vy_supplies", "mark": "main?"}],
    "ashroad/wen": [{"if": "ar_warden", "unless": "ar_spire_done", "mark": "main?"}],
    "solgard/odo": [{"unless": "sg_odo", "mark": "main!"}],
    "solgard/tomas": [{"if": "sg_overseer", "unless": "sg_tomas2", "mark": "main?"}],
    "heart/rhenn": [{"if": "sg_end", "unless": "eh_captain", "mark": "main!"}],
    "heart/regent": [{"if": "eh_parley", "unless": "eh_regent", "mark": "main!"}],
    "dawn/tomas_d": [{"if": "eh_end", "unless": "dn_tomas", "mark": "main!"}],
    "dawn/counsel_d": [{"if": "dn_tomas", "unless": "dn_watch", "mark": "main!"}],
    "hushmere/sorrel": [{"if": "eg_leth_go", "unless": "hs_welcome", "mark": "main!"}],
    "hushmere/merrow": [{"if": "hs_neris", "unless": "hs_official", "mark": "main!"}],
    "hushmere/neris": [{"if": "hs_official", "unless": "hs_end", "mark": "main?"}],
    "lowerhush/oriel": [{"if": "lh_woman", "unless": "lh_choice", "mark": "main!"}],
    "lowerhush/corrow": [{"if": "lh_warden", "unless": "lh_corrow", "mark": "main!"}],
    "songhall/maren_a": [{"if": "sh_speech", "unless": "sh_walk", "mark": "main!"}],
    "songhall/maren_b": [{"if": "sh_walk", "unless": "sh_end", "mark": "main!"}],
    "ashroad/hesk_b": [{"if": "ar_hesk", "unless": "ar_end", "mark": "main?"}],
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
