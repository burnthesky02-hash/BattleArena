using System;
using System.Collections.Generic;

namespace BattleArenaPrototype
{
    // Mirrors summon_server.py's JSON shapes exactly. JsonUtility can
    // deserialize these because every field is a primitive, a List<T> of a
    // [Serializable] type, or another [Serializable] type -- no Dictionary,
    // which JsonUtility can't handle.

    [Serializable]
    public class StateResponse
    {
        public int gems;
        public int roster_size;
        public Costs costs;
    }

    [Serializable]
    public class Costs
    {
        public int character_1x;
        public int character_10x;
        public int equipment_1x;
        public int equipment_10x;
    }

    [Serializable]
    public class CharacterResult
    {
        public string rarity;
        public string name;
        public string class_id;
        public bool is_duplicate;
        public int shards_gained;
        public string message;
    }

    [Serializable]
    public class EquipmentResult
    {
        public string rarity;
        public string name;
        public string slot;
        public string message;
    }

    // Two separate response classes (rather than one generic<T>) because
    // JsonUtility can't deserialize a generic List<T> field whose T varies
    // at runtime -- it needs the concrete field type known at compile time.
    [Serializable]
    public class CharacterSummonResponse
    {
        public bool ok;
        public string message;
        public int gems;
        public List<CharacterResult> results;
    }

    [Serializable]
    public class EquipmentSummonResponse
    {
        public bool ok;
        public string message;
        public int gems;
        public List<EquipmentResult> results;
    }
}
