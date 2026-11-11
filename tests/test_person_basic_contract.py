"""Owner核准的生日／任職語意，不需要正式資料庫就能驗證輸入契約。"""
import pytest
from pydantic import ValidationError


@pytest.mark.parametrize('value',[{}, {'birth_month':4,'birth_day':12}, {'birth_year':1998,'birth_month':4,'birth_day':12}, {'birth_month':2,'birth_day':29}, {'birth_year':2000,'birth_month':2,'birth_day':29}])
def test_birthdays_valid(value):
    from app.person_details_schemas import BirthdayValue
    data=BirthdayValue(**value)
    assert data.birth_year==value.get('birth_year')


@pytest.mark.parametrize('value',[{'birth_year':1998}, {'birth_month':4}, {'birth_day':12}, {'birth_month':2,'birth_day':31}, {'birth_year':1900,'birth_month':2,'birth_day':29}, {'birth_year':2023,'birth_month':2,'birth_day':29}, {'birth_month':13,'birth_day':1}, {'birth_month':0,'birth_day':1}, {'birth_month':4,'birth_day':31}, {'birth_year':True,'birth_month':1,'birth_day':1}])
def test_birthdays_invalid(value):
    from app.person_details_schemas import BirthdayValue
    with pytest.raises(ValidationError):BirthdayValue(**value)


def test_employments_keep_independent_unknown_dates():
    from app.person_details_schemas import EmploymentValue
    first=EmploymentValue(company_name='第一組織',employment_status='current')
    second=EmploymentValue(job_title='自由工作者',employment_status='current')
    assert first.valid_from is None and first.valid_to is None
    assert first.company_name=='第一組織' and second.job_title=='自由工作者'


@pytest.mark.parametrize('payload',[{}, {'company_name':'  ','job_title':' '}, {'company_name':'組織','valid_from':'2026-02-01','valid_to':'2025-12-31'}])
def test_employment_invalid(payload):
    from app.person_details_schemas import EmploymentValue
    with pytest.raises(ValidationError):EmploymentValue(**payload)


def test_self_recorded_source_does_not_invent_evidence():
    from app.person_details_schemas import PersonDetailSource
    data=PersonDetailSource(source_kind='manual')
    assert data.source_experience_id is None and data.evidence_type is None
