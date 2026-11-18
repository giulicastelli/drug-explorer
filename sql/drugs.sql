-- Run by the loader after the labels are in.
-- The class of an ingredient is the most common one among its labels.
INSERT INTO drugs
SELECT substance_key,
       count(*),
       count(*) FILTER (WHERE product_type = 'Rx'),
       count(*) FILTER (WHERE product_type = 'OTC'),
       mode() WITHIN GROUP (ORDER BY pharm_class_epc) FILTER (WHERE pharm_class_epc IS NOT NULL)
FROM labels
GROUP BY substance_key;
