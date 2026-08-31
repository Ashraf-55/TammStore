"""Offline contract checks for the v15 domain frontend/backend integration.
These checks do not require Flask/network dependencies; they validate that the
frontend calls the v15 domain endpoints and that the backend exposes them.
"""
from pathlib import Path
import ast, re, sqlite3, tempfile, os

ROOT=Path(__file__).parent
js=(ROOT/'frontend/app.js').read_text()
source=(ROOT/'routes/domain_routes.py').read_text()
enterprise=(ROOT/'routes/enterprise_routes.py').read_text()
required_api=[
 '/employees','/departments','/positions','/workspace/users','/clients/','/projects/','/projects/${id}/members',
 '/projects/${id}/milestones','/projects/${id}/deliverables','/projects/${id}/financials','/projects/${id}/workspace','/projects/${projectId}/budget','/projects/${projectId}/expenses',
 '/client/me','/client/projects','/client/requests','/requests/','/requests/${id}/assign','/requests/${id}/resolve'
]
for endpoint in required_api:
    assert endpoint in js, f'frontend missing API contract: {endpoint}'
for endpoint in ['/employees','/departments','/positions','/workspace/users','/clients/<int:client_id>/contacts','/projects/<int:project_id>/members',
                 '/projects/<int:project_id>/milestones','/projects/<int:project_id>/deliverables',
                 '/projects/<int:project_id>/financials','/projects/<int:project_id>/workspace','/projects/<int:project_id>/budget','/projects/<int:project_id>/expenses','/client/me','/client/projects','/client/requests',
                 '/requests/<int:request_id>/assign','/requests/<int:request_id>/resolve']:
    assert endpoint in source, f'backend missing route contract: {endpoint}'

# AST-level route sanity: every domain route has a function body.
tree=ast.parse(source)
route_count=0
for node in tree.body:
    if isinstance(node,ast.FunctionDef):
        if any(isinstance(d,ast.Call) and isinstance(d.func,ast.Attribute) and d.func.attr=='route' for d in node.decorator_list):
            route_count += 1
assert route_count >= 20, route_count

# Fresh DB migration/schema smoke test without importing Flask.
from subprocess import run, PIPE
with tempfile.TemporaryDirectory() as td:
    db=os.path.join(td,'smoke.db')
    r=run(['python','migrate.py','up'],cwd=ROOT,env={**os.environ,'CODELA_DB_PATH':db},stdout=PIPE,stderr=PIPE,text=True)
    assert r.returncode==0, r.stderr or r.stdout
    c=sqlite3.connect(db)
    version=c.execute('select max(version) from schema_migrations').fetchone()[0]
    assert version==18, version
    tables=['employees','roles','permissions','user_roles','client_contacts','client_users','project_members','project_milestones','project_deliverables','project_approvals','task_time_entries','project_costs','project_budgets','files','file_links','conversations','students','instructors']
    for table in tables:
        assert c.execute("select 1 from sqlite_master where type='table' and name=?",(table,)).fetchone(), table
    c.close()
assert '/search' in enterprise and '/reports/overview' in enterprise and '/client/dashboard' in enterprise
print(f'PASS: frontend/backend domain contract ({route_count} domain routes + enterprise layer), migration v18, and schema smoke test')
