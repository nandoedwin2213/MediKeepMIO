"""Metabolic risk engine models: versioned clinical config, assessments and history."""

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from .base import Base, get_utc_now


class MetabolicEngineConfig(Base):
    """Versioned clinical configuration (ranges, criteria, score weights, alerts)."""

    __tablename__ = "metabolic_engine_configs"

    id = Column(Integer, primary_key=True)
    version = Column(Integer, nullable=False, unique=True, index=True)
    config = Column(JSON, nullable=False)
    notes = Column(Text, nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=get_utc_now, nullable=False)


class MetabolicAssessment(Base):
    """Snapshot of one engine run with every input, range and version used."""

    __tablename__ = "metabolic_assessments"

    id = Column(Integer, primary_key=True)
    patient_id = Column(
        Integer,
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assessed_at = Column(DateTime, default=get_utc_now, nullable=False, index=True)
    algorithm_version = Column(String(20), nullable=False)
    config_version = Column(Integer, nullable=False)
    fingerprint = Column(String(64), nullable=False)
    score = Column(Float, nullable=True)
    risk_level = Column(String(20), nullable=True)
    metabolic_syndrome_status = Column(String(20), nullable=True)
    result = Column(JSON, nullable=False)
    source = Column(String(20), default="auto", nullable=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)


class MetabolicProfile(Base):
    """Metabolic history: personal/family background, habits, limitations and goals."""

    __tablename__ = "metabolic_profiles"

    id = Column(Integer, primary_key=True)
    patient_id = Column(
        Integer,
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    has_diabetes = Column(Boolean, nullable=True)
    has_prediabetes = Column(Boolean, nullable=True)
    has_hypertension = Column(Boolean, nullable=True)
    has_dyslipidemia = Column(Boolean, nullable=True)
    has_fatty_liver = Column(Boolean, nullable=True)
    has_obesity = Column(Boolean, nullable=True)
    has_cardiovascular_disease = Column(Boolean, nullable=True)
    family_diabetes = Column(Boolean, nullable=True)

    physical_activity_minutes_week = Column(Integer, nullable=True)
    sitting_hours_day = Column(Float, nullable=True)
    sleep_hours = Column(Float, nullable=True)
    alcohol = Column(String(20), nullable=True)  # none, occasional, weekly, daily
    smoking = Column(String(20), nullable=True)  # never, former, current
    sugary_drinks_per_week = Column(Integer, nullable=True)
    ultraprocessed_per_week = Column(Integer, nullable=True)
    fruit_veg_servings_day = Column(Integer, nullable=True)

    musculoskeletal_limitations = Column(Text, nullable=True)
    pain_level = Column(Integer, nullable=True)  # 0-10
    goals = Column(Text, nullable=True)
    diet_pattern = Column(String(20), nullable=True)  # omnivore, vegetarian, ...
    food_intolerances = Column(Text, nullable=True)
    food_dislikes = Column(Text, nullable=True)
    meals_per_day = Column(Integer, nullable=True)

    updated_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=get_utc_now, nullable=False)
    updated_at = Column(
        DateTime, default=get_utc_now, onupdate=get_utc_now, nullable=False
    )


class FunctionalAssessment(Base):
    """Simple functional tests (sit-to-stand, grip, gait speed, 6-minute walk, RPE)."""

    __tablename__ = "functional_assessments"

    id = Column(Integer, primary_key=True)
    patient_id = Column(
        Integer,
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assessed_at = Column(DateTime, nullable=False, index=True)
    sit_to_stand_30s = Column(Integer, nullable=True)
    grip_strength_kg = Column(Float, nullable=True)
    gait_speed_m_s = Column(Float, nullable=True)
    walk_test_m = Column(Float, nullable=True)
    rpe = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=get_utc_now, nullable=False)


class ExercisePlan(Base):
    """Structured exercise prescription; patients only see it once a professional approves it."""

    __tablename__ = "exercise_plans"

    id = Column(Integer, primary_key=True)
    patient_id = Column(
        Integer,
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = Column(
        String(20), default="draft", nullable=False
    )  # draft/approved/archived
    plan = Column(JSON, nullable=False)
    rationale = Column(JSON, nullable=True)
    generator_version = Column(String(30), nullable=True)
    notes = Column(Text, nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=get_utc_now, nullable=False)
    updated_at = Column(
        DateTime, default=get_utc_now, onupdate=get_utc_now, nullable=False
    )


class NutritionPlan(Base):
    """Structured nutrition plan; patients only see it once a professional approves it."""

    __tablename__ = "nutrition_plans"

    id = Column(Integer, primary_key=True)
    patient_id = Column(
        Integer,
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = Column(String(20), default="draft", nullable=False)
    plan = Column(JSON, nullable=False)
    rationale = Column(JSON, nullable=True)
    generator_version = Column(String(30), nullable=True)
    notes = Column(Text, nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=get_utc_now, nullable=False)
    updated_at = Column(
        DateTime, default=get_utc_now, onupdate=get_utc_now, nullable=False
    )


class Recipe(Base):
    """Recipe library entry; nutrition values are per serving."""

    __tablename__ = "recipes"

    id = Column(Integer, primary_key=True)
    slug = Column(String(80), unique=True, nullable=False, index=True)
    name = Column(String(150), nullable=False)
    category = Column(String(20), nullable=False, index=True)
    description = Column(Text, nullable=True)
    servings = Column(Integer, default=1, nullable=False)
    prep_minutes = Column(Integer, nullable=True)
    kcal = Column(Float, nullable=True)
    protein_g = Column(Float, nullable=True)
    carbs_g = Column(Float, nullable=True)
    fat_g = Column(Float, nullable=True)
    fiber_g = Column(Float, nullable=True)
    diets = Column(JSON, nullable=False, default=list)
    allergens = Column(JSON, nullable=False, default=list)
    tags = Column(JSON, nullable=False, default=list)
    ingredients = Column(JSON, nullable=False, default=list)
    steps = Column(JSON, nullable=False, default=list)
    image_url = Column(String(500), nullable=True)
    image_credit = Column(String(300), nullable=True)
    image_source_url = Column(String(500), nullable=True)
    language = Column(String(10), default="es", nullable=False)
    is_library = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=get_utc_now, nullable=False)
    updated_at = Column(
        DateTime, default=get_utc_now, onupdate=get_utc_now, nullable=False
    )


class AdherenceLog(Base):
    """Daily/weekly checklist entries of the patient's programme (one row per item and day)."""

    __tablename__ = "adherence_logs"
    __table_args__ = (
        UniqueConstraint(
            "patient_id", "log_date", "item", name="uq_adherence_patient_date_item"
        ),
    )

    id = Column(Integer, primary_key=True)
    patient_id = Column(
        Integer,
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    log_date = Column(Date, nullable=False, index=True)
    item = Column(String(30), nullable=False)
    done = Column(Boolean, default=True, nullable=False)
    value = Column(Float, nullable=True)
    source = Column(String(20), default="patient", nullable=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=get_utc_now, nullable=False)
    updated_at = Column(
        DateTime, default=get_utc_now, onupdate=get_utc_now, nullable=False
    )


class MetabolicInsight(Base):
    """FISAI Metabolic AI explanation; patients only see it once a professional approves it."""

    __tablename__ = "metabolic_insights"

    id = Column(Integer, primary_key=True)
    patient_id = Column(
        Integer,
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = Column(String(20), default="draft", nullable=False)
    content = Column(JSON, nullable=False)
    note = Column(Text, nullable=True)
    engine_version = Column(String(30), nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=get_utc_now, nullable=False)
    updated_at = Column(
        DateTime, default=get_utc_now, onupdate=get_utc_now, nullable=False
    )
