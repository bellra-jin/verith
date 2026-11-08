"""Immutable analysis boundaries; stdlib only, no agent/auth/persistence imports."""
from dataclasses import dataclass
from datetime import datetime,timedelta
import hashlib
import json
import math
import re
from typing import Literal
from uuid import UUID

AnalysisState=Literal['running','result_ready','stored','failed','unknown','deleted']


class AnalysisContractError(ValueError):
    def __init__(self):super().__init__('Analysis adapter contract is invalid')


def canonical_json(value):
    def check(item):
        if isinstance(item,dict):
            if not all(isinstance(key,str) for key in item):raise AnalysisContractError()
            for child in item.values():check(child)
        elif isinstance(item,list):
            for child in item:check(child)
        elif type(item) not in {str,int,float,bool,type(None)}:raise AnalysisContractError()
        elif isinstance(item,float) and not math.isfinite(item):raise AnalysisContractError()
    try:
        check(value)
        return json.dumps(value,ensure_ascii=False,allow_nan=False,sort_keys=True,separators=(',',':'))
    except (TypeError,ValueError,UnicodeError,RecursionError):raise AnalysisContractError() from None


def json_hash(text):
    try:return hashlib.sha256(text.encode('utf8')).hexdigest()
    except (AttributeError,UnicodeError):raise AnalysisContractError() from None


def strict_json(text):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise AnalysisContractError()
            result[key]=value
        return result
    def finite_float(value):
        result=float(value)
        if not math.isfinite(result):raise AnalysisContractError()
        return result
    try:
        if not isinstance(text,str):raise AnalysisContractError()
        text.encode('utf8')
        return json.loads(text,object_pairs_hook=pairs,parse_float=finite_float,parse_constant=lambda _:(_ for _ in ()).throw(AnalysisContractError()))
    except (TypeError,ValueError,UnicodeError,RecursionError):raise AnalysisContractError() from None


@dataclass(frozen=True,slots=True)
class AnalysisContext:
    analysis_id:UUID
    admission_request_id:UUID
    attempt_id:UUID
    owner_user_id:UUID
    operation:str
    input_fingerprint:str
    as_of:datetime
    deadline_at:datetime

    def __post_init__(self):self.validate()

    def validate(self):
        if not all(isinstance(value,UUID) for value in (self.analysis_id,self.admission_request_id,self.attempt_id,self.owner_user_id)):
            raise AnalysisContractError()
        if (not isinstance(self.operation,str) or not self.operation or len(self.operation)>128
                or any(ord(c)<33 or ord(c)>126 for c in self.operation)
                or not isinstance(self.input_fingerprint,str) or not re.fullmatch('[0-9a-f]{64}',self.input_fingerprint)):
            raise AnalysisContractError()
        for value in (self.as_of,self.deadline_at):
            if not isinstance(value,datetime) or value.utcoffset()!=timedelta(0):raise AnalysisContractError()

    def identity(self):
        self.validate()
        return dict(analysis_id=str(self.analysis_id),admission_request_id=str(self.admission_request_id),
            attempt_id=str(self.attempt_id),owner_user_id=str(self.owner_user_id),operation=self.operation,
            input_fingerprint=self.input_fingerprint,as_of=self.as_of.isoformat(),deadline_at=self.deadline_at.isoformat())


@dataclass(frozen=True,slots=True)
class StagedReportReference:
    report_id:UUID
    owner_user_id:UUID

    def __post_init__(self):
        if not isinstance(self.report_id,UUID) or not isinstance(self.owner_user_id,UUID):raise AnalysisContractError()


@dataclass(frozen=True,slots=True)
class FrozenAnalysisResult:
    context:AnalysisContext
    report_id:UUID
    input_schema:str
    result_schema:str
    input_json:str
    input_sha256:str
    result_json:str
    result_sha256:str
    binding_sha256:str

    @staticmethod
    def _binding(context,report_id,input_schema,result_schema,input_sha256,result_sha256):
        return json_hash(canonical_json(dict(context=context.identity(),report_id=str(report_id),
            input_schema=input_schema,result_schema=result_schema,input_sha256=input_sha256,result_sha256=result_sha256)))

    @classmethod
    def freeze(cls,*,context,report_id,input_schema,result_schema,input_json,result_json):
        if not isinstance(context,AnalysisContext) or not isinstance(report_id,UUID):raise AnalysisContractError()
        a,b=json_hash(input_json),json_hash(result_json)
        return cls(context,report_id,input_schema,result_schema,input_json,a,result_json,b,
            cls._binding(context,report_id,input_schema,result_schema,a,b))

    def __post_init__(self):self.validate()

    def validate(self):
        if not isinstance(self.context,AnalysisContext) or not isinstance(self.report_id,UUID):raise AnalysisContractError()
        self.context.validate()
        for value in (self.input_schema,self.result_schema):
            if not isinstance(value,str) or not re.fullmatch('[A-Za-z0-9_.-]{1,128}',value):raise AnalysisContractError()
        for text,digest in ((self.input_json,self.input_sha256),(self.result_json,self.result_sha256)):
            if not isinstance(digest,str) or not re.fullmatch('[0-9a-f]{64}',digest):raise AnalysisContractError()
            decoded=strict_json(text)
            if not isinstance(decoded,dict) or canonical_json(decoded)!=text or json_hash(text)!=digest:raise AnalysisContractError()
        if self.binding_sha256!=self._binding(self.context,self.report_id,self.input_schema,self.result_schema,self.input_sha256,self.result_sha256):
            raise AnalysisContractError()
