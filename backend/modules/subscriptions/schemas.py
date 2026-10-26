from datetime import date
from pydantic import BaseModel, Field, model_validator
class OfferIn(BaseModel):
    name:str=Field(min_length=3,max_length=120)
    code:str=Field(min_length=3,max_length=60,pattern=r'^[A-Za-z0-9_-]+$')
    description:str|None=None
    discount_pct:float=Field(default=0,ge=0,le=100)
    bonus_days:int=Field(default=0,ge=0,le=730)
    max_redemptions:int|None=Field(default=None,ge=1)
    starts_on:date
    ends_on:date
    @model_validator(mode='after')
    def check(self):
        if self.ends_on<self.starts_on:raise ValueError('Offer end date must not precede start date')
        if not self.discount_pct and not self.bonus_days:raise ValueError('Specify a discount or bonus days')
        return self
