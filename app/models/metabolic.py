"""Metabolic risk engine models: versioned clinical config, assessments and history."""

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
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

    updated_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=get_utc_now, nullable=False)
    updated_at = Column(
        DateTime, default=get_utc_now, onupdate=get_utc_now, nullable=False
    )
