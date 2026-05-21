CREATE TRIGGER testruns_runid_trigger
AFTER INSERT ON testruns
FOR EACH ROW
WHEN (NEW.runid IS NULL OR NEW.runid = '')
BEGIN
    UPDATE testruns
    SET testruns.runid = strftime('%Y%m%d_%H%M%f', 'now') || '_' || NEW.id
    WHERE id = NEW.id;
END;
