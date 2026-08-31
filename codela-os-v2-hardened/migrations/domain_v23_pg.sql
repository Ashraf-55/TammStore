-- Codela OS v23: register the 'deliverables.approve' permission code
-- (backing the fix that gates POST /deliverables/<id>/approval).
INSERT INTO permissions(code,description) VALUES
('deliverables.approve','Request/manage deliverable approval workflow')
ON CONFLICT(code) DO NOTHING;
