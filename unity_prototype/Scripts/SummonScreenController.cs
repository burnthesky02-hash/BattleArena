using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

namespace BattleArenaPrototype
{
    /// <summary>
    /// Orchestrates the prototype Summon screen: banner buttons pick
    /// Character vs Equipment, x1/x10 buttons hit summon_server.py, and the
    /// results spawn as face-down RevealCard prefabs that "Reveal All"
    /// flips with a small stagger. This mirrors data/hero_rarity.py's
    /// HERO_RARITY_COLOR values directly so a pull's color matches what
    /// the real pygame build already uses.
    /// </summary>
    public class SummonScreenController : MonoBehaviour
    {
        [Header("API")]
        public SummonApiClient api;

        [Header("UI")]
        public Text gemsText;
        public Text statusText;
        public Transform revealGridParent;   // a GameObject with a GridLayoutGroup
        public RevealCard revealCardPrefab;
        public Button revealAllButton;
        public Button continueButton;
        public Button pullCharacter1xButton;
        public Button pullCharacter10xButton;
        public Button pullEquipment1xButton;
        public Button pullEquipment10xButton;

        [Header("Timing")]
        public float staggerSeconds = 0.12f;

        private readonly List<RevealCard> _spawnedCards = new List<RevealCard>();

        // Matches data/hero_rarity.py's HERO_RARITY_COLOR exactly (0-255 -> 0-1).
        // Equipment rarities ("epic"/"legendary") reuse the same table since
        // the names overlap; equipment has no "common"/"rare" pulls via Summon.
        private static readonly Dictionary<string, Color32> RarityColors = new Dictionary<string, Color32>
        {
            { "common",    new Color32(190, 190, 195, 255) },
            { "rare",      new Color32(90, 170, 230, 255) },
            { "epic",      new Color32(185, 110, 230, 255) },
            { "legendary", new Color32(235, 175, 60, 255) },
            { "mythic",    new Color32(230, 60, 90, 255) },
        };

        private void Awake()
        {
            pullCharacter1xButton.onClick.AddListener(() => PullCharacter(1));
            pullCharacter10xButton.onClick.AddListener(() => PullCharacter(10));
            pullEquipment1xButton.onClick.AddListener(() => PullEquipment(1));
            pullEquipment10xButton.onClick.AddListener(() => PullEquipment(10));
            revealAllButton.onClick.AddListener(RevealAll);
            continueButton.onClick.AddListener(ClearCards);
            revealAllButton.gameObject.SetActive(false);
            continueButton.gameObject.SetActive(false);
        }

        private void Start()
        {
            RefreshState();
        }

        private void RefreshState()
        {
            api.GetState(
                onSuccess: state =>
                {
                    gemsText.text = $"Gems: {state.gems}";
                    statusText.text =
                        $"Character x1: {state.costs.character_1x}   x10: {state.costs.character_10x}\n" +
                        $"Equipment x1: {state.costs.equipment_1x}   x10: {state.costs.equipment_10x}";
                },
                onError: err => statusText.text = $"Couldn't reach summon_server.py: {err}"
            );
        }

        private void SetPullButtonsInteractable(bool interactable)
        {
            pullCharacter1xButton.interactable = interactable;
            pullCharacter10xButton.interactable = interactable;
            pullEquipment1xButton.interactable = interactable;
            pullEquipment10xButton.interactable = interactable;
        }

        private void PullCharacter(int count)
        {
            ClearCards();
            SetPullButtonsInteractable(false);
            api.SummonCharacter(count,
                onSuccess: resp =>
                {
                    SetPullButtonsInteractable(true);
                    gemsText.text = $"Gems: {resp.gems}";
                    if (!resp.ok)
                    {
                        statusText.text = resp.message;
                        return;
                    }
                    statusText.text = resp.message;
                    foreach (var r in resp.results)
                    {
                        string tag = r.is_duplicate ? $"+{r.shards_gained} shards" : "NEW!";
                        Color32 color = RarityColors.TryGetValue(r.rarity, out var c) ? c : RarityColors["common"];
                        SpawnCard($"{r.name}\n({r.class_id})", CapitalizeRarity(r.rarity), color, tag);
                    }
                    ShowRevealControls(true);
                },
                onError: err =>
                {
                    SetPullButtonsInteractable(true);
                    statusText.text = err;
                });
        }

        private void PullEquipment(int count)
        {
            ClearCards();
            SetPullButtonsInteractable(false);
            api.SummonEquipment(count,
                onSuccess: resp =>
                {
                    SetPullButtonsInteractable(true);
                    gemsText.text = $"Gems: {resp.gems}";
                    if (!resp.ok)
                    {
                        statusText.text = resp.message;
                        return;
                    }
                    statusText.text = resp.message;
                    foreach (var r in resp.results)
                    {
                        Color32 color = RarityColors.TryGetValue(r.rarity, out var c) ? c : RarityColors["common"];
                        SpawnCard(r.name, CapitalizeRarity(r.rarity), color, r.slot);
                    }
                    ShowRevealControls(true);
                },
                onError: err =>
                {
                    SetPullButtonsInteractable(true);
                    statusText.text = err;
                });
        }

        private void SpawnCard(string displayName, string rarityLabel, Color32 color, string tag)
        {
            RevealCard card = Instantiate(revealCardPrefab, revealGridParent);
            card.ResetCard();
            card.SetBackContent(displayName, rarityLabel, color, tag);
            _spawnedCards.Add(card);
        }

        private void ShowRevealControls(bool show)
        {
            revealAllButton.gameObject.SetActive(show);
            continueButton.gameObject.SetActive(show);
        }

        private void RevealAll()
        {
            StartCoroutine(RevealAllStaggered());
        }

        private IEnumerator RevealAllStaggered()
        {
            foreach (var card in _spawnedCards)
            {
                card.Reveal();
                yield return new WaitForSeconds(staggerSeconds);
            }
        }

        private void ClearCards()
        {
            foreach (var card in _spawnedCards)
            {
                if (card != null) Destroy(card.gameObject);
            }
            _spawnedCards.Clear();
            ShowRevealControls(false);
        }

        private static string CapitalizeRarity(string rarity)
        {
            if (string.IsNullOrEmpty(rarity)) return rarity;
            return char.ToUpperInvariant(rarity[0]) + rarity.Substring(1);
        }
    }
}
