from sqlalchemy import Column, String, Boolean, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()
engine = create_engine("sqlite:///clusters.db")
SessionLocal = sessionmaker(bind=engine)

class ClusterConfig(Base):
    __tablename__ = "cluster_configs"
    name = Column(String, primary_key=True)
    hostname = Column(String)
    network = Column(String, default="")  
    metallbinstalled = Column(Boolean, default=False)
    istioinstalled = Column(Boolean, default=False)

def init_db():
    Base.metadata.create_all(bind=engine)
