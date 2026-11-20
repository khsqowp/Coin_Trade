"""Mechanical spec/plugin implementation coverage audit."""
import json

FIELD_MAP={"entry_long":"entry_long","entry_short":"entry_short","exit":"exit","stop_loss":"stop_loss","take_profit":"take_profit","filters":"filters","position_sizing":"position_sizing","timeframes":"timeframes"}
def audit(spec_path, plugin):
    spec=json.loads(open(spec_path,encoding="utf-8").read()); implemented=set(getattr(plugin,"IMPLEMENTED_FIELDS",[])); deviations=list(getattr(plugin,"DEVIATIONS",[]))
    present=[]
    for field,key in FIELD_MAP.items():
        if key in spec or field in spec: present.append(field)
    unimplemented=[x for x in present if x not in implemented]
    warn=bool((not deviations and spec.get("mechanical_spec_complete") is False) or unimplemented)
    return {"spec_id":spec.get("id",spec.get("spec_id","")),"present_fields":present,"implemented_fields":sorted(implemented),"unimplemented_fields":unimplemented,"deviations":deviations,"status":"WARN" if warn else "OK"}
