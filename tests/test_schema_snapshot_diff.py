"""Schema比較不得因表數相同漏掉型別、約束或預設值差異。"""
from copy import deepcopy
import importlib.util
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('snapshot_diff',Path(__file__).resolve().parents[1]/'scripts/compare_schema_snapshots.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def snapshot():
    return {'structure':{'columns':[{'table':'people','name':'name','type':'text','nullable':False,'default':None}],'constraints':[{'table':'people','name':'pk','definition':'PRIMARY KEY (id)'}]},'effective_runtime_privileges':[]}


@pytest.mark.parametrize('field,value',[('type','jsonb'),('nullable',True),('default',"'unknown'")])
def test_equal_counts_do_not_hide_column_drift(field,value):
    a=snapshot();b=deepcopy(a);b['structure']['columns'][0][field]=value
    result=module.compare(a,b)
    assert not result['structure_equal'] and result['structure_diff']['columns']['only_alpha']
    assert result['fingerprints_sha256']['alpha']!=result['fingerprints_sha256']['e2e']


def test_metadata_difference_is_not_silently_called_identical():
    a=snapshot();b=deepcopy(a);a['migration_receipts']='old receipts';b['migration_receipts']='010 only'
    result=module.compare(a,b)
    assert result['structure_equal'] and not result['metadata_diff']['migration_receipts']['equal']
