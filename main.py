from start_files.app import create_app


app = create_app()

#if __name__ == "__main__":
    
#    import uvicorn
#    uvicorn.run(app, host="127.0.0.1", port=5000)
#    gunicorn -w 4 -k uvicorn.workers.UvicornWorke
#nohup uvicorn main:app --host 0.0.0.0 --port 5000 --reload --log-level debug
#sudo nano /etc/systemd/system/fastapi.service 
#systemctl daemon-reload
#sudo nano /etc/systemd/system/fastapi.service 


