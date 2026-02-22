from fastapi import APIRouter



router = APIRouter(prefix="/home")


@router.get("/")
def home():
    return{"message":"welcome to the nextgen bank api"}