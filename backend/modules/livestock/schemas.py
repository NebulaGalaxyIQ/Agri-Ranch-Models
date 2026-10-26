"""V8 domain validation. No changes to V6 request contracts."""
from datetime import date
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field, model_validator

Currency = Literal['TZS', 'USD', 'KES', 'EUR']

class Targeted(BaseModel):
    group_id: int | None = Field(default=None, gt=0)
    animal_id: int | None = Field(default=None, gt=0)
    @model_validator(mode='after')
    def one_target(self):
        if (self.group_id is None) == (self.animal_id is None):
            raise ValueError('Select one animal or one herd/flock, not both')
        return self

class HouseIn(BaseModel):
    ranch_id: int = Field(gt=0)
    code: str = Field(min_length=2, max_length=80)
    name: str = Field(min_length=2, max_length=160)
    house_type: Literal['barn','paddock','shed','coop','brooder','layer_house','free_range','stable','other'] = 'barn'
    species: str | None = Field(default=None, max_length=80)
    capacity: int = Field(gt=0)
    location: str | None = Field(default=None, max_length=180)

class PlaceGroupIn(BaseModel):
    group_id: int = Field(gt=0)
    house_id: int = Field(gt=0)
    moved_on: date = Field(default_factory=date.today)
    notes: str | None = Field(default=None, max_length=2000)

class CareIn(Targeted):
    activity: Literal['feeding','watering','cleaning','bedding','inspection','grazing','milking','egg_collection_check','biosecurity','other']
    shift: Literal['morning','afternoon','evening','night'] = 'morning'
    performed_on: date = Field(default_factory=date.today)
    quantity: Decimal | None = Field(default=None, gt=0)
    unit: str | None = Field(default=None, max_length=30)
    expense: Decimal = Field(default=Decimal('0'), ge=0)
    currency: Currency = 'TZS'
    reference: str = Field(min_length=8, max_length=120)
    notes: str | None = None
    @model_validator(mode='after')
    def quantity_unit(self):
        if self.quantity is not None and not self.unit:
            raise ValueError('Specify unit when entering quantity')
        return self

class BreedingIn(Targeted):
    method: Literal['natural','ai','synchronization','other'] = 'natural'
    sire_tag: str | None = Field(default=None, max_length=100)
    service_date: date = Field(default_factory=date.today)
    expected_date: date | None = None
    outcome: Literal['planned','served','confirmed','delivered','failed'] = 'served'
    notes: str | None = None
    @model_validator(mode='after')
    def dates(self):
        if self.expected_date and self.expected_date < self.service_date:
            raise ValueError('Expected birth date cannot precede breeding')
        return self

class HealthIn(Targeted):
    action: Literal['vaccination','deworming','treatment','checkup','diagnosis','quarantine','other']
    condition: str | None = Field(default=None, max_length=160)
    medication: str | None = Field(default=None, max_length=160)
    dosage: str | None = Field(default=None, max_length=100)
    status: Literal['planned','completed'] = 'completed'
    performed_on: date = Field(default_factory=date.today)
    next_due: date | None = None
    cost: Decimal = Field(default=Decimal('0'), ge=0)
    currency: Currency = 'TZS'
    notes: str | None = None
    @model_validator(mode='after')
    def dates(self):
        if self.next_due and self.next_due < self.performed_on:
            raise ValueError('Next due date cannot precede action date')
        if self.status == 'planned' and self.cost:
            raise ValueError('Record expenses when treatment is completed')
        return self

class WeightIn(Targeted):
    measured_on: date = Field(default_factory=date.today)
    weight_kg: Decimal = Field(gt=0)
    sample_size: int = Field(default=1, ge=1)
    notes: str | None = None
    @model_validator(mode='after')
    def sample(self):
        if self.animal_id is not None and self.sample_size != 1:
            raise ValueError('Individual animal weight has sample size 1')
        return self

class IncubationIn(BaseModel):
    group_id: int = Field(gt=0)
    batch_code: str = Field(min_length=2, max_length=100)
    eggs_set: int = Field(gt=0)
    set_on: date = Field(default_factory=date.today)
    expected_on: date
    notes: str | None = None
    @model_validator(mode='after')
    def dates(self):
        if self.expected_on < self.set_on:
            raise ValueError('Expected hatch must follow setting date')
        return self

class HatchIn(BaseModel):
    hatched_on: date = Field(default_factory=date.today)
    eggs_hatched: int = Field(ge=0)
    notes: str | None = None

class BreedingOutcomeIn(BaseModel):
    outcome: Literal['planned','served','confirmed','delivered','failed']
    notes: str | None = None

class CompleteHealthIn(BaseModel):
    performed_on: date = Field(default_factory=date.today)
    cost: Decimal = Field(default=Decimal('0'), ge=0)
    currency: Currency = 'TZS'
    notes: str | None = None

# V8.3 strict connected registration and repeating-operation contracts.
class OptionalCharge(BaseModel):
    quantity: Decimal | None = Field(default=None, gt=0)
    unit: str = Field(default='head', min_length=1, max_length=40)
    unit_cost: Decimal | None = Field(default=None, ge=0)
    description: str | None = Field(default=None, max_length=240)
    currency: Currency = 'TZS'
    @model_validator(mode='after')
    def complete_cost(self):
        if (self.quantity is None) != (self.unit_cost is None):
            raise ValueError('Cost quantity and price per unit must be entered together')
        return self

class ConnectedGroupIn(BaseModel):
    project_id: int = Field(gt=0)
    name: str = Field(min_length=2,max_length=160)
    species: str = Field(min_length=2,max_length=80)
    breed: str | None = Field(default=None,max_length=100)
    purpose: Literal['general','breeding','dairy','egg_production','meat','wool','rearing','other'] = 'general'
    production_stage: str | None = Field(default=None,max_length=60)
    head_count: int = Field(ge=0)
    location: str | None = Field(default=None,max_length=180)
    notes: str | None = None
    charge: OptionalCharge | None = None

class ConnectedIndividualIn(BaseModel):
    group_id: int = Field(gt=0)
    tag: str | None = Field(default=None,max_length=100)
    sex: Literal['male','female','unknown'] = 'unknown'
    birth_date: date | None = None
    origin: str | None = Field(default=None,max_length=200)
    offspring_cohort_id: int | None = Field(default=None,gt=0)
    dam_id: int | None = Field(default=None,gt=0)
    sire_id: int | None = Field(default=None,gt=0)
    characteristics: str | None = None
    initial_weight_kg: Decimal | None = Field(default=None,gt=0)
    charge: OptionalCharge | None = None

class ConnectedHouseIn(BaseModel):
    group_id: int = Field(gt=0)
    code: str = Field(min_length=2,max_length=80)
    name: str = Field(min_length=2,max_length=160)
    house_type: Literal['barn','paddock','shed','coop','brooder','layer_house','broiler_house','free_range','stable']
    capacity: int = Field(gt=0)
    location: str | None = Field(default=None,max_length=180)
    assign_now: bool = False
    charge: OptionalCharge | None = None

class RoutineTemplateIn(BaseModel):
    group_id: int = Field(gt=0)
    name: str = Field(min_length=2,max_length=160)
    activity: Literal['feeding','watering','cleaning','bedding','inspection','grazing','milking','egg_collection_check','biosecurity','medication','other']
    shift: Literal['morning','afternoon','evening','night'] = 'morning'
    reminder_time: str | None = Field(default=None,pattern=r'^([01]\d|2[0-3]):[0-5]\d$')
    days_of_week: str = Field(default='0123456', min_length=1, max_length=7,pattern=r'^[0-6]+$')
    starts_on: date = Field(default_factory=date.today)
    default_quantity: Decimal | None = Field(default=None,gt=0)
    unit: str | None = Field(default=None,max_length=30)
    default_expense: Decimal = Field(default=Decimal('0'),ge=0)
    currency: Currency = 'TZS'
    instructions: str | None = None
    @model_validator(mode='after')
    def check_quantity(self):
        if self.default_quantity is not None and not self.unit: raise ValueError('Quantity requires a unit')
        if len(set(self.days_of_week)) != len(self.days_of_week): raise ValueError('Weekdays cannot repeat')
        return self

class RoutineCompleteIn(BaseModel):
    completed_on: date = Field(default_factory=date.today)
    quantity: Decimal | None = Field(default=None,ge=0)
    expense: Decimal | None = Field(default=None,ge=0)
    notes: str | None = None

class RoutineToggleIn(BaseModel):
    active: bool

class ConnectedBreedingIn(BaseModel):
    group_id: int = Field(gt=0)
    animal_id: int | None = Field(default=None,gt=0)
    method: Literal['natural','ai','synchronization','other'] = 'natural'
    sire_tag: str | None = Field(default=None,max_length=100)
    service_date: date = Field(default_factory=date.today)
    expected_date: date | None = None
    outcome: Literal['planned','served','confirmed','failed'] = 'served'
    notes: str | None = None
    charge: OptionalCharge | None = None
    @model_validator(mode='after')
    def date_check(self):
        if self.expected_date and self.expected_date < self.service_date:raise ValueError('Expected delivery cannot precede mating date')
        return self

class BreedingProgressIn(BaseModel):
    outcome: Literal['served','confirmed','failed','cancelled']
    event_on: date = Field(default_factory=date.today)
    notes: str | None = None

class OffspringIn(BaseModel):
    born_on: date = Field(default_factory=date.today)
    total_born: int = Field(ge=0)
    live_count: int = Field(ge=0)
    male_count: int | None = Field(default=None,ge=0)
    female_count: int | None = Field(default=None,ge=0)
    cohort_name: str = Field(min_length=2,max_length=160)
    initial_weight_kg: Decimal | None = Field(default=None,gt=0)
    characteristics: str | None = None
    notes: str | None = None
    charge: OptionalCharge | None = None
    @model_validator(mode='after')
    def counts(self):
        if self.live_count>self.total_born:raise ValueError('Live offspring cannot exceed total born')
        if self.male_count is not None and self.female_count is not None and self.male_count+self.female_count>self.live_count:
            raise ValueError('Sex count cannot exceed live offspring')
        return self

class ConnectedIncubationIn(BaseModel):
    group_id: int = Field(gt=0)
    breeding_id: int | None = Field(default=None,gt=0)
    batch_code: str = Field(min_length=2,max_length=100)
    eggs_set: int = Field(gt=0)
    set_on: date = Field(default_factory=date.today)
    expected_on: date | None = None
    notes: str | None = None
    charge: OptionalCharge | None = None
    @model_validator(mode='after')
    def date_checks(self):
        if self.expected_on and self.expected_on < self.set_on:
            raise ValueError('Expected hatch date cannot precede egg-setting date')
        return self
