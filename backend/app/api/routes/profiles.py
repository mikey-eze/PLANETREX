"""Read-only results. Scientific collection is deliberately admin CLI only."""
from typing import Literal
from fastapi import APIRouter, HTTPException, Query
from app.pipeline.core import get_profile, list_profiles, search

router=APIRouter(prefix='/science',tags=['Stored scientific profiles'])

@router.get('/profiles')
def profiles(body:Literal['earth','moon','mars'],limit:int=Query(50,ge=1,le=200),offset:int=Query(0,ge=0)) -> dict:
    items=list_profiles(body,limit,offset)
    return {'body':body,'profiles':items,'count':len(items),'source':'local stored data only'}

@router.get('/profiles/{profile_id:path}')
def profile(profile_id:str) -> dict:
    item=get_profile(profile_id)
    if item is None:raise HTTPException(404,'Stored profile not found')
    return item

@router.get('/candidates')
def candidates(reference_id:str,limit:int=Query(50,ge=1,le=200),offset:int=Query(0,ge=0)) -> dict:
    try:return search(reference_id,limit,offset)
    except LookupError as exc:raise HTTPException(404,str(exc)) from exc
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc
