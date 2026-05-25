UPDATE topic_paper_notes SET source = '' WHERE source IS NULL;

DELETE FROM topic_paper_notes
WHERE id NOT IN (
    SELECT MAX(id)
    FROM topic_paper_notes
    GROUP BY paper_id, topic_id, note_type, source
);

DROP INDEX IF EXISTS idx_topic_paper_notes_unique;

CREATE UNIQUE INDEX IF NOT EXISTS idx_topic_paper_notes_unique_source
ON topic_paper_notes(paper_id, topic_id, note_type, source);
