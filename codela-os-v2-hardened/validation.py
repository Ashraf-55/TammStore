from functools import wraps
from flask import request, jsonify, g

MAX_JSON_BYTES=512*1024; MAX_STRING=10000; MAX_ARRAY=1000; MAX_OBJECT_KEYS=100; MAX_DEPTH=8

def _walk(value, depth=0):
    if depth>MAX_DEPTH: raise ValueError("payload nesting is too deep")
    if isinstance(value,str) and len(value)>MAX_STRING: raise ValueError("string value exceeds maximum length")
    if isinstance(value,list):
        if len(value)>MAX_ARRAY: raise ValueError("array exceeds maximum length")
        for x in value:_walk(x,depth+1)
    elif isinstance(value,dict):
        if len(value)>MAX_OBJECT_KEYS: raise ValueError("too many object fields")
        for k,x in value.items():
            if not isinstance(k,str) or len(k)>128: raise ValueError("invalid object field name")
            _walk(x,depth+1)

def before_request_validation():
    if request.content_length and request.content_length>MAX_JSON_BYTES:return jsonify({"error":"Request payload too large","code":"payload_too_large"}),413
    if request.method in {"POST","PUT","PATCH"} and request.is_json:
        try:
            body=request.get_json(silent=False) or {}; _walk(body); g.json_body=body
        except Exception as exc:return jsonify({"error":"Invalid JSON payload","code":"invalid_json","details":str(exc)}),400

def json_body():
    body=getattr(g,"json_body",None)
    if body is None: body=request.get_json(silent=True) or {}; _walk(body); g.json_body=body
    return body

def pagination(default_limit=50,max_limit=100):
    try: page=max(1,int(request.args.get("page",1))); limit=min(max_limit,max(1,int(request.args.get("limit",default_limit))))
    except (TypeError,ValueError): raise ValueError("page and limit must be integers")
    return page,limit,(page-1)*limit

def validate_fields(data,allowed=None,required=None):
    allowed=set(allowed or data.keys()); required=set(required or ())
    unknown=set(data)-allowed; missing=required-set(data)
    if unknown: raise ValueError("unexpected fields: "+", ".join(sorted(unknown)))
    if missing: raise ValueError("missing required fields: "+", ".join(sorted(missing)))
    return data

def strict_json(schema):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args,**kwargs):
            try: body=json_body()
            except ValueError as exc:return jsonify({"error":str(exc),"code":"validation_error"}),400
            if not isinstance(body,dict): return jsonify({"error":"JSON object required","code":"validation_error"}),400
            unknown=set(body)-set(schema)
            if unknown:return jsonify({"error":"Unexpected fields: "+", ".join(sorted(unknown)),"code":"unexpected_fields"}),400
            for name,spec in schema.items():
                typ,required,max_len=spec
                if required and name not in body:return jsonify({"error":f"{name} is required","code":"validation_error"}),400
                if name not in body:continue
                value=body[name]
                if not isinstance(value,typ):return jsonify({"error":f"{name} has invalid type","code":"validation_error"}),400
                if isinstance(value,str) and len(value)>max_len:return jsonify({"error":f"{name} exceeds maximum length","code":"validation_error"}),400
            g.json_body=body; return fn(*args,**kwargs)
        return wrapper
    return decorator
