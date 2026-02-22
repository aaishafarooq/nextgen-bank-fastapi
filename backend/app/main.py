from fastapi import FastAPI


app = FastAPI(
    title=" NextGen Bank - FastAPI",
    description="Fully features banking api built with fastapi ",
)
@app.get("/")
def home():
    return{"message":"welcome to the nextgen bank api"}