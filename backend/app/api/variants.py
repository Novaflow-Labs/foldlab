"""Variants router — real generation via services.variants.generate.

Loads the base sequence via services.sequences.get_sequence, then generates
variants. Keeps the route/response_model as the contract.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from ..db import get_session
from ..schemas import VariantGenerateRequest, VariantGenerateResponse
from ..services import sequences as seq_svc
from ..services import variants as variants_svc

router = APIRouter(prefix="/variants", tags=["variants"])


@router.post("/generate", response_model=VariantGenerateResponse)
def generate_variants(
    req: VariantGenerateRequest, session: Session = Depends(get_session)
) -> VariantGenerateResponse:
    base = seq_svc.get_sequence(session, req.base_sequence_id)
    if base is None:
        raise HTTPException(status_code=404, detail="base sequence not found")
    try:
        variants = variants_svc.generate(base.residues, req.strategy, req.params)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return VariantGenerateResponse(base_sequence_id=req.base_sequence_id, variants=variants)
