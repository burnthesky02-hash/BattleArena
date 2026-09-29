using System.Collections;
using UnityEngine;
using UnityEngine.UI;

namespace BattleArenaPrototype
{
    /// <summary>
    /// One face-down/face-up reveal card. Flip is done by shrinking the
    /// front face away on the Y axis, swapping which child is active, then
    /// growing the back face in -- this avoids ever rendering mirrored text
    /// (the classic "180-degree flip" bug), at the cost of being a slightly
    /// simpler motion than a true continuous flip. Good enough to judge
    /// whether Unity's animation feel beats pygame's instant reveal -- that
    /// is the actual question this prototype is testing.
    /// </summary>
    public class RevealCard : MonoBehaviour
    {
        [Header("Wiring (see unity_prototype/README.md for prefab layout)")]
        public RectTransform cardTransform;
        public GameObject frontFace;   // shows the face-down "?" card back
        public GameObject backFace;    // shows the revealed result, starts inactive
        public Image backBanner;       // tinted by rarity
        public Text nameText;
        public Text rarityText;
        public Text tagText;           // "NEW!" / "+N shards" / equipment slot

        [HideInInspector] public bool revealed;

        public void SetBackContent(string displayName, string rarityLabel, Color rarityColor, string tag)
        {
            if (nameText != null) nameText.text = displayName;
            if (rarityText != null) rarityText.text = rarityLabel;
            if (backBanner != null) backBanner.color = rarityColor;
            if (tagText != null) tagText.text = tag;
        }

        public void ResetCard()
        {
            revealed = false;
            if (cardTransform != null) cardTransform.localRotation = Quaternion.identity;
            if (frontFace != null) frontFace.SetActive(true);
            if (backFace != null) backFace.SetActive(false);
        }

        /// <summary>Hook this to the card's own Button.onClick for
        /// click-to-flip, in addition to any "Reveal All" button.</summary>
        public void OnCardClicked()
        {
            Reveal();
        }

        public void Reveal(float duration = 0.35f)
        {
            if (revealed) return;
            revealed = true;
            StartCoroutine(FlipCoroutine(duration));
        }

        private IEnumerator FlipCoroutine(float duration)
        {
            float half = duration / 2f;

            float t = 0f;
            while (t < half)
            {
                t += Time.deltaTime;
                float angle = Mathf.Lerp(0f, 90f, t / half);
                cardTransform.localRotation = Quaternion.Euler(0f, angle, 0f);
                yield return null;
            }

            frontFace.SetActive(false);
            backFace.SetActive(true);

            t = 0f;
            while (t < half)
            {
                t += Time.deltaTime;
                float angle = Mathf.Lerp(90f, 0f, t / half);
                cardTransform.localRotation = Quaternion.Euler(0f, angle, 0f);
                yield return null;
            }
            cardTransform.localRotation = Quaternion.identity;
        }
    }
}
