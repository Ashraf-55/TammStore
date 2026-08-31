from jobs import register
@register("automation.fire_event")
def automation(payload,job):
 from automation import fire_event_sync
 fire_event_sync(payload["event_name"],payload["tenant_id"],payload.get("context"))
@register("communication.send")
def communication(payload,job):
 from routes.communication_routes import send_via_adapter
 from database import get_db
 c=get_db();r=send_via_adapter(c,job["tenant_id"],payload["channel"],payload["to"],payload.get("subject"),payload["body"],payload.get("lead_id"),payload.get("client_id"),payload.get("user_id"));c.commit();c.close();return r
@register("publish.content")
def publish(payload,job):
 from routes.publish_routes import ADAPTERS
 from secret_store import decrypt_secret
 from database import get_db
 c=get_db();tid=job["tenant_id"];content=c.execute("SELECT * FROM content_ideas WHERE id=? AND tenant_id=?",(payload["content_id"],tid)).fetchone()
 if not content:c.close();raise ValueError("Content not found")
 platform=payload.get("platform") or content["platform"];con=c.execute("SELECT * FROM platform_connections WHERE tenant_id=? AND platform=? AND is_active=1",(tid,platform)).fetchone();ok,eid,err,mode=ADAPTERS[platform](access_token=decrypt_secret(con["access_token"]) if con and con["access_token"] else None).publish(content,payload.get("caption",content["hook"]));c.execute("INSERT INTO publish_log (tenant_id,content_id,platform,status,external_post_id,error_message,mode) VALUES (?,?,?,?,?,?,?)",(tid,content["id"],platform,"published" if ok else "failed",eid,err,mode));c.commit();c.close();
 if not ok:raise RuntimeError(err or "publish failed")

