using System;
using System.Collections;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;

namespace BattleArenaPrototype
{
    /// <summary>
    /// Thin wrapper around UnityWebRequest for talking to the local
    /// summon_server.py prototype API (see that file's own docstring).
    /// Desktop Editor Play mode isn't a browser, so CORS doesn't apply here
    /// -- this only becomes a concern if this project is later built for
    /// WebGL, which is out of scope for this prototype.
    /// </summary>
    public class SummonApiClient : MonoBehaviour
    {
        [Tooltip("Must match summon_server.py's HOST/PORT constants.")]
        public string baseUrl = "http://127.0.0.1:8765";

        public void GetState(Action<StateResponse> onSuccess, Action<string> onError)
        {
            StartCoroutine(GetJson<StateResponse>("/state", onSuccess, onError));
        }

        public void SummonCharacter(int count, Action<CharacterSummonResponse> onSuccess, Action<string> onError)
        {
            StartCoroutine(PostJson<CharacterSummonResponse>("/summon/character", count, onSuccess, onError));
        }

        public void SummonEquipment(int count, Action<EquipmentSummonResponse> onSuccess, Action<string> onError)
        {
            StartCoroutine(PostJson<EquipmentSummonResponse>("/summon/equipment", count, onSuccess, onError));
        }

        private IEnumerator GetJson<T>(string route, Action<T> onSuccess, Action<string> onError)
        {
            using (UnityWebRequest req = UnityWebRequest.Get(baseUrl + route))
            {
                yield return req.SendWebRequest();
                HandleResponse(req, onSuccess, onError);
            }
        }

        private IEnumerator PostJson<T>(string route, int count, Action<T> onSuccess, Action<string> onError)
        {
            string body = "{\"count\":" + count + "}";
            byte[] bodyBytes = Encoding.UTF8.GetBytes(body);

            using (UnityWebRequest req = new UnityWebRequest(baseUrl + route, "POST"))
            {
                req.uploadHandler = new UploadHandlerRaw(bodyBytes);
                req.downloadHandler = new DownloadHandlerBuffer();
                req.SetRequestHeader("Content-Type", "application/json");
                yield return req.SendWebRequest();
                HandleResponse(req, onSuccess, onError);
            }
        }

        private void HandleResponse<T>(UnityWebRequest req, Action<T> onSuccess, Action<string> onError)
        {
#if UNITY_2020_2_OR_NEWER
            bool failed = req.result != UnityWebRequest.Result.Success;
#else
            bool failed = req.isNetworkError || req.isHttpError;
#endif
            if (failed)
            {
                onError?.Invoke($"{req.error} (is summon_server.py running on {baseUrl}?)");
                return;
            }

            try
            {
                T parsed = JsonUtility.FromJson<T>(req.downloadHandler.text);
                onSuccess?.Invoke(parsed);
            }
            catch (Exception e)
            {
                onError?.Invoke($"Failed to parse response: {e.Message}\nRaw: {req.downloadHandler.text}");
            }
        }
    }
}
