


app = FastAPI(tittle="JusAds Compliance LangGraph API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_headers=["*"],
    allow_methods=["*"],
)

app.include_router(remix_router, prefix="/remix")

s3 = boto3.client("boto3-runtime", s3)

UPLOAD_DIR = Path("asseys/uploads")
CLIPS_DIR = Path("assets/clips")
RESULTS_DIR = Path("assets/result")

def node_router