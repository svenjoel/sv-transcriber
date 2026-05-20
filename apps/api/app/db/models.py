from sqlalchemy import String, Integer, Float, ForeignKey, Text, Column
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class Media(Base):
    __tablename__ = "media"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(512))
    path: Mapped[str] = mapped_column(String(2048))
    transcript = Column(Text)

class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    media_id: Mapped[int] = mapped_column(ForeignKey("media.id"))
    status: Mapped[str] = mapped_column(String(32), default="queued")
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    message: Mapped[str] = mapped_column(String(512), default="")
    transcript_id: Mapped[str] = mapped_column(String(64), default="")

    media = relationship("Media")

class Transcript(Base):
    __tablename__ = "transcripts"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    media_id: Mapped[int] = mapped_column(ForeignKey("media.id"))
    language: Mapped[str] = mapped_column(String(16), default="sv")
    json_blob: Mapped[str] = mapped_column(Text)

    media = relationship("Media")

class SpeakerProfile(Base):
    __tablename__ = "speaker_profiles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)

    # JSON list of floats (embedding vector)
    embedding_json = Column(Text, nullable=False)

    # number of enrollment updates (we keep a running average)
    n_updates = Column(Integer, nullable=False, default=1)