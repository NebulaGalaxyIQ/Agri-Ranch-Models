from __future__ import annotations
from datetime import date
from pydantic import BaseModel, Field, ConfigDict, model_validator
from typing import Literal

class ReportFilter(BaseModel):
    model_config=ConfigDict(extra='forbid')
    from_date: date|None=None
    to_date: date|None=None
    date_field: str|None=Field(default=None,max_length=60)
    project_id: int|None=Field(default=None,ge=1)
    ranch_id: int|None=Field(default=None,ge=1)
    batch_id: int|None=Field(default=None,ge=1)
    group_id: int|None=Field(default=None,ge=1)
    cycle_id: int|None=Field(default=None,ge=1)
    animal_id: int|None=Field(default=None,ge=1)
    item_id: int|None=Field(default=None,ge=1)
    machine_id: int|None=Field(default=None,ge=1)
    trial_id: int|None=Field(default=None,ge=1)
    lot_id: int|None=Field(default=None,ge=1)
    field_id: int|None=Field(default=None,ge=1)
    house_id: int|None=Field(default=None,ge=1)
    species: str|None=Field(default=None,max_length=80)
    status: str|None=Field(default=None,max_length=60)
    currency: str|None=Field(default=None,max_length=10)
    search: str|None=Field(default=None,max_length=100)
    @model_validator(mode='after')
    def dates(self):
        if self.from_date and self.to_date and self.from_date>self.to_date:
            raise ValueError('Start date cannot exceed end date')
        return self

class ReportRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    section_id: str=Field(min_length=2,max_length=64)
    filters: ReportFilter=Field(default_factory=ReportFilter)
    dataset: str|None=Field(default=None,max_length=90)
    page: int=Field(default=1,ge=1,le=1000000)
    page_size: int=Field(default=40,ge=1,le=200)
    order: Literal['asc','desc']='desc'
    sort_by: str|None=Field(default=None,max_length=80)

class ExportRequest(ReportRequest):
    format: Literal['pdf','xlsx','csv']='pdf'
    mode: Literal['complete','detailed','summary']='complete'
    include_charts: bool=True
    include_finance: bool=True
    paper: Literal['a4','a3','letter']='a3'
    orientation: Literal['landscape','portrait']='landscape'

class SavedReportIn(BaseModel):
    model_config=ConfigDict(extra='forbid')
    title: str=Field(min_length=2,max_length=160)
    section_id: str=Field(min_length=2,max_length=64)
    configuration: dict=Field(default_factory=dict)
    visibility: Literal['private','organization']='private'

class ScheduleIn(BaseModel):
    model_config=ConfigDict(extra='forbid')
    saved_report_id: int=Field(ge=1)
    cadence: Literal['daily','weekly','monthly']
    timezone: str=Field(default='UTC',min_length=2,max_length=64)
    format: Literal['pdf','xlsx']='pdf'
