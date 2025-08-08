from datetime import datetime

from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped, mapped_column
from data.settings import Settings
import sqlalchemy as sa

class Base(DeclarativeBase):
    pass

class Wallet(Base):
    __tablename__ = 'wallets'

    id: Mapped[int] = mapped_column(primary_key=True)
    private_key: Mapped[str] = mapped_column(unique=True, index=True)
    address: Mapped[str] = mapped_column(unique=True)
    proxy: Mapped[str] = mapped_column(default=None, nullable=True)
    proxy_status: Mapped[str] = mapped_column(default="OK", nullable=True)
    discord_token: Mapped[str] = mapped_column(default=None, nullable=True)
    twitter_token: Mapped[str] = mapped_column(default=None, nullable=True)
    twitter_status: Mapped[str] = mapped_column(default="OK", nullable=True)
    completed_quests: Mapped[str] = mapped_column(nullable=True, default="")
    ref_code: Mapped[str] = mapped_column(nullable=True, default=None)
    account_blocked: Mapped[bool] = mapped_column(default=False, server_default=sa.false(), nullable=False)
    last_faucet_claim: Mapped[datetime | None] = mapped_column(default=None)


    def __repr__(self):
        if Settings().hide_wallet_address_log:
            return f'[{self.id}]'
        return f'[{self.id}][{self.address}]'
