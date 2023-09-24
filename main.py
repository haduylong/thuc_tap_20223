from fastapi import FastAPI, HTTPException, Depends, status, Request, Response, Header
from pathlib import Path
from pydantic import BaseModel
from typing import Annotated
import models
from models import Device, Record
from database import engine, SessionLocal
from sqlalchemy.orm import Session

from onvif import WsDiscoveryClient, OnvifClient
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, FileResponse
import subprocess
import ffmpeg

import cv2
import os.path
import shutil
import aiortc
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from aiortc.rtcrtpsender import RTCRtpSender
from aiortc.mediastreams import MediaStreamError
from av.video.frame import VideoFrame
from aiortc.contrib.media import MediaBlackhole, MediaPlayer, MediaRecorder, MediaRelay


import json
import asyncio
import traceback
import numpy as np
import time
import multiprocessing
import threading
import uuid

ROOT = os.path.dirname(__file__)
record_folder = 'records'

app = FastAPI()

'''
database
'''
models.Base.metadata.create_all(bind=engine)

class DeviceBase(BaseModel):
    name : str
    ipaddress : str
    port : int = 80
    username : str = 'admin'
    password : str = 'songnam@123'
    subnet : str = '8'
    macaddress : str
    datelimit : int = 10
    timelimit : int = 1

class RecordBase(BaseModel):
    timestart: str
    timeend: str
    macaddress: str
    storage : str

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]

'''
variable
'''

listScanDevice = [] # list[dict{ip, port}] danh sách thiết bị scan được
listDevice = [] # 
listRecords = []
live_devices = {}
ptz_devices = {} # {ip : [onvif_client, profile]}

def getDeviceInformation(username, password, port, ipaddress):
    info = {}
    try: 
        onvif_client = OnvifClient(ip_address=ipaddress, port=port, user_name=username, password=password)
        onvif_camera = onvif_client._onvif_camera
        # {Manufacturer, Model, FirmwareVersion, SerialNumber (device id), HardwareId}
        info1 = onvif_camera.devicemgmt.GetDeviceInformation()
        # mac address
        mac_info = onvif_camera.devicemgmt.GetNetworkInterfaces()[0].Info.HwAddress
        submask = onvif_camera.devicemgmt.GetNetworkInterfaces()[0].IPv4.Config.Manual[0].PrefixLength
        #
        # uri = onvif_camera.devicemgmt.GetCapabilities()['Device']['XAddr']
        # 
        info['ipaddress'] = ipaddress
        info['port'] = port
        info['username'] = username
        info['password'] = password
        info['manufacturer'] = info1.Manufacturer
        info['model'] = info1.Model
        info['firmwareVersion'] = info1.FirmwareVersion
        info['device id'] = info1.SerialNumber
        info['hardwareId'] = info1.HardwareId
        info['macaddress'] = mac_info
        info['submask'] = submask
        # info['uri'] = uri
        return info
    except Exception:
        traceback.print_exc()
    finally:
        return info

'''
quét tìm thiết bị trong mạng LAN
'''
# tìm toàn bộ ip thiết bị trong mạng lan
# trên windows
def get_mac_address_windows(ip_address):
    arp_command = ['arp', '/a', ip_address]
    output = subprocess.check_output(arp_command).decode()
    mac_address = output.split()[-2]
    return mac_address
# trên linux
def get_mac_address_unix(ip_address):
    arp_command = ['arp', '-n', ip_address]
    output = subprocess.check_output(arp_command).decode()
    mac_address = output.split()[3]
    return mac_address

def scanDevice(result : list):
    global listScanDevice
    wds_client = WsDiscoveryClient()
    listScanDevice = wds_client.search()
    wds_client.dispose()

    for scanDevice in listScanDevice:
        mac = get_mac_address_windows(scanDevice.ip_address)
        result.append({
            'ipaddress': scanDevice.ip_address,
            'port': scanDevice.port,
            'macaddress': mac
        })

@app.get("/devices/scan", status_code=status.HTTP_200_OK)
async def scan_device():
    result = []
    try:
        scanDevice(result)
        return result
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=400, detail="ERROR")


'''
crud thiết bị
'''
# thêm thiết bị vào database
@app.post("/devices", status_code=status.HTTP_201_CREATED)
async def create_device(device: DeviceBase, db: db_dependency):
    try:
        # db_device = models.Device(**device.dict())
        info = getDeviceInformation(username=device.username, password=device.password, ipaddress=device.ipaddress, port=device.port)
        if len(info) == 0:
            raise HTTPException(status_code=404, detail="Device not found")
        else:
            db_device = Device()
            db_device.name = device.name
            db_device.ipaddress = info['ipaddress']
            db_device.port = info['port']
            db_device.username = info['username']
            db_device.password = info['password']
            db_device.subnet = info['submask']
            db_device.macaddress = info['macaddress']
            db_device.datelimit = device.datelimit
            db_device.timelimit = device.timelimit
            db.add(db_device)
            db.commit()
            return db_device
    except Exception:
        traceback.print_exc()

# lấy thiết bị từ database bằng ip
@app.get("/devices/get/{ipaddress}", status_code=status.HTTP_200_OK)
async def read_device_by_ip(ipaddress: str, db: db_dependency):
    try:
        device = db.query(models.Device).filter(models.Device.ipaddress == ipaddress).first()
        if device is None:
            raise HTTPException(status_code=404, detail="Device not found") 
        return device.__dict__
    except Exception:
        traceback.print_exc()

# lấy ra tất cả thiết bị
def getAllDevice():
    session = SessionLocal()
    devices = session.query(Device).all()
    return devices

@app.get("/devices/get-all-device", status_code=status.HTTP_200_OK)
async def read_all_device(db: db_dependency):
    try:
        results = []
        devices = db.query(Device).all()
        for x in devices:
            results.append(x.__dict__)
        return results
    except Exception:
        traceback.print_exc()

# xoá thiết bị khỏi database
@app.delete("/devices/delete/{ipaddress}", status_code=status.HTTP_200_OK)
async def delete_device(ipaddress: str, db: db_dependency):
    device = db.query(models.Device).filter(models.Device.ipaddress == ipaddress).first()
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found") 
    db.delete(device)
    db.commit()

# xoá tất cả thiết bị
async def delete_all_devices(db: db_dependency):
    db.query(models.Device).delete()
    db.commit()

@app.delete("/devices/delete_all", status_code=status.HTTP_200_OK)
async def delete_device(db: db_dependency):
    delete_all_devices(db)

# ptz điều khiển xoay thiết bị
def moveAction(ipaddress: str ,move_action: str):
    liveDevice = live_devices[ipaddress]
    onvif_client = OnvifClient(liveDevice.ipaddress, liveDevice.port, liveDevice.username, liveDevice.password)
    # onvif_client = OnvifClient('192.168.1.110', 80, 'admin', 'songnam@123')
    profile_tokens = onvif_client.get_profile_tokens()
    profile_token = profile_tokens[0]

    match move_action:
        case 'up':
            onvif_client.move_tilt(profile_token, 1)
        case 'up-left':
            onvif_client._move(profile_token, pan_velocity=-1, tilt_velocity=1)
        case 'up-right':
            onvif_client._move(profile_token, pan_velocity= 1, tilt_velocity=1)
        case 'right':
            onvif_client.move_pan(profile_token, velocity= 1)
        case 'left':
            onvif_client.move_pan(profile_token, velocity=-1)
        case 'down':
            onvif_client.move_tilt(profile_token, velocity=-1)
        case 'down-left':
            onvif_client._move(profile_token, pan_velocity=-1, tilt_velocity=-1)
        case 'down-right':
            onvif_client._move(profile_token, pan_velocity= 1, tilt_velocity=-1)
        case 'in':
            onvif_client.move_zoom(profile_token, velocity= 1)
        case 'out':
            onvif_client.move_zoom(profile_token, velocity=-1)
        case 'stop':
            onvif_client.stop_ptz(profile_token)

@app.get("/devices/ptz/{ipaddress}/{move_action}", status_code=status.HTTP_200_OK)
async def move_actions(ipaddress: str ,move_action: str):
    try:
        thread = threading.Thread(target=moveAction, args=(ipaddress, move_action))
        thread.start()
        # thread.join()
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=400, detail="ERROR")

'''
crud record
'''
# lấy ra tất cả các record của thiết bị
def getRecordByMac(macaddress: str):
    session = SessionLocal()
    records = session.query(Record).filter(Record.macaddress == macaddress).all()
    return records

@app.get("/records/get-record-device/{macaddress}", status_code=status.HTTP_200_OK)
async def read_all_device_record(macaddress: str):
    try:
        # result = db.query(Record).filter(Record.macaddress == macaddress).all()
        result = []
        records = getRecordByMac(macaddress)
        for record in records:
            result.append(record.__dict__)
        return result
    except Exception:
        traceback.print_exc()

'''
live stream #########################################################
'''
# index.html
@app.get("/", status_code=status.HTTP_200_OK)
async def index():
    content = open(os.path.join(ROOT, "index.html"), "r").read()
    return HTMLResponse(content=content, status_code=200)

# scripts.html
@app.get("/scripts.js", status_code=status.HTTP_200_OK)
async def scripts():
    content = open(os.path.join(ROOT, "scripts.js"), "r").read()
    return Response(content=content, status_code=200)

# live
pcs = set() # peer connection set 

# Tạo lớp VideoStreamTrack để lưu trữ khung hình video
class CameraVideoTrack(VideoStreamTrack):
    """
    A video track that reads frames from a camera.
    """
    def __init__(self, device_id=0):
        super().__init__()        
        self.device_id = device_id
        self.cap = cv2.VideoCapture(self.device_id)
        self._id = str(uuid.uuid4())
        self.__ended = False
        # self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        # self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    async def recv(self) -> VideoFrame:
        """
        Receive the next :class:`~av.video.frame.VideoFrame`.
        """
        # Read frame from camera
        ret, frame = self.cap.read()
        if not ret:
            raise MediaStreamError

        # Convert frame to VideoFrame
        pts, time_base = await self.next_timestamp()
        video_frame = VideoFrame.from_ndarray(frame, format="bgr24")
        video_frame.pts = pts
        video_frame.time_base = time_base

        return video_frame



def force_codec(pc, sender, forced_codec):
    kind = forced_codec.split("/")[0]
    codecs = RTCRtpSender.getCapabilities(kind).codecs
    transceiver = next(t for t in pc.getTransceivers() if t.sender == sender)
    transceiver.setCodecPreferences(
        [codec for codec in codecs if codec.mimeType == forced_codec]
    )

# stream video từ một thiết bị ra internet
@app.post("/devices/live/{ipaddress}", status_code=status.HTTP_200_OK)
async def live(ipaddress: str, db: db_dependency, request: Request):
    try:
        device = db.query(models.Device).filter(models.Device.ipaddress == ipaddress).first()
        if device is None:
            raise HTTPException(status_code=404, detail="Device not found")
        liveDevice = device
        live_devices[ipaddress] = device

        onvif_client = OnvifClient(liveDevice.ipaddress, liveDevice.port, liveDevice.username, liveDevice.password)
        profile_tokens = onvif_client.get_profile_tokens()
        profile_token = profile_tokens[0]
        streamUri = onvif_client.get_streaming_uri(profile_token)

        uri = streamUri[:7]+liveDevice.username+':'+liveDevice.password+'@'+streamUri[7:]

        params = await request.json()
        offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

        pc = RTCPeerConnection()
        pcs.add(pc)
        
        @pc.on("connectionstatechange")
        async def on_connectionstatechange():
            print("Connection state is %s" % pc.connectionState)
            if pc.connectionState == "failed":
                await pc.close()
                pcs.discard(pc)

        video = CameraVideoTrack(uri)

        if video:
            video_sender = pc.addTrack(video)
            force_codec(pc, video_sender, "video/H264")

        await pc.setRemoteDescription(offer)

        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)

        return JSONResponse(
            {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
        )
    except Exception:
        traceback.print_exc()

'''
____________________________________________________________________
'''

'''
ghi hình #########################################################
'''
# recording vào máy tính multi threading
threads = {} # dict[{ip : thread}]
finish = {} # dict[{ip : isFinish}]

def count_folders(folder_path):
    folder_count = 0
    for _, dirs, _ in os.walk(folder_path):
        folder_count += len(dirs)
        break
    if(folder_count> 0):
        return folder_count, os.path.join(folder_path, dirs[0]), dirs[0]
    else:
        return folder_count, None, None

def recording_thread(ipaddress: str): 
    # lấy thông tin camera từ database   
    session = SessionLocal()
    device = session.query(models.Device).filter(models.Device.ipaddress == ipaddress).first()
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    # kết nối đến camera
    onvif_client = OnvifClient(device.ipaddress, device.port, device.username, device.password)
    profile_tokens = onvif_client.get_profile_tokens()
    profile_token = profile_tokens[0]
    streamUri = onvif_client.get_streaming_uri(profile_token)

    rtsp_url = streamUri[:7]+device.username+':'+device.password+'@'+streamUri[7:] 
    # cấu trúc lưu trữ   record_folder/device.name/date(Y-m-d)/time_start timeend.mp4
    # folder chứa date record của thiết bị
    devicePath = os.path.join(ROOT, record_folder ,device.name) # record_folder/device.name
    if not os.path.exists(devicePath):
        os.makedirs(devicePath)

    # Create a VideoCapture object
    capture = cv2.VideoCapture(rtsp_url)
    totalframe = 0
    # Default resolutions of the frame are obtained (system dependent)
    frame_width = int(capture.get(3))
    frame_height = int(capture.get(4))
    codec = cv2.VideoWriter_fourcc(*'MP4V')
    # loop tạo folder date trong folder name_device
    # date_count = 0 # kiểm tra số ngày ghi
    while not finish[ipaddress]:
        # kiểm tra số ngày vượt quá giới hạn
        number_folder_date, first_date_devicePath, date = count_folders(devicePath) # số ngày, ngày ghi sớm nhất (path), ngày ghi sớm nhất
        if number_folder_date > 10:
            shutil.rmtree(first_date_devicePath) # xoá thư mục date
            rows_to_delete = session.query(Record).filter((Record.storage.like(f'%{date}%'))).all()
            for row in rows_to_delete:
                session.delete(row)
            session.commit()
        #tạo date folder mới
        date_record = time.strftime("%Y-%m-%d")
        date_devicePath = os.path.join(devicePath, date_record) # record_folder/device.name/date(Y-m-d)
        if not os.path.exists(date_devicePath):
            os.makedirs(date_devicePath)
    # loop tạo file trong date folder
        while(not finish[ipaddress]):
            totalframe = 0
            # tạo tên file luu video
            start_time_string = time.strftime("%Y-%m-%d %H-%M-%S")
            date_record = start_time_string.split(' ')[0]
            output_file = os.path.join(date_devicePath ,start_time_string + '.mp4')
            # 25 frame per second
            output_video = cv2.VideoWriter(output_file, codec, fps=25, frameSize=(frame_width, frame_height)) 
            # ghi frame vào file
            while(not finish[ipaddress]):
                if capture.isOpened() and totalframe != 250:
                    (status, frame) = capture.read()
                    totalframe +=1    
                    output_video.write(frame) 
                    print(totalframe)
                else:
                    break
            # thêm thông tin record vào database
            record = models.Record()
            record.timestart = start_time_string
            record.timeend = time.strftime("%Y-%m-%d %H-%M-%S")
            check_date = record.timeend.split(' ')[0]
            record.macaddress = device.macaddress
            storage = output_file[:-4] + ' ' + record.timeend.split(' ')[1] + '.mp4' # records/name_device/date(Y-m-d)/time_start timeend.mp4
            record.storage = storage
            session.add(record)
            session.commit()   
            print('luu thanh cong')
            # capture.release()
            output_video.release()
            os.rename(src=output_file, dst=storage)
            # kiểm tra có phải ngày mới không
            if(check_date > date_record):
                break

@app.get("/devices/record-thread/start/{ipaddress}")
async def start_record_thread(ipaddress: str):
    global threads
    global finish

    try:
        t = threading.Thread(target=recording_thread, args=((ipaddress,)))
        threads[ipaddress] = t
        finish[ipaddress] = False
        threads[ipaddress].start()
    except Exception:
        traceback.print_exc()
    
    return {"message": "Processing started"}

@app.get("/devices/record-thread/stop/{ipaddress}")
async def stop_record_thread(ipaddress : str):
    global threads
    global finish
    finish[ipaddress] = True
    threads[ipaddress].join()
    del finish[ipaddress]
    del threads[ipaddress]
    return 'thread join'

@app.post("/records/live/{macaddress}/{timestart}/{timeend}", status_code=status.HTTP_200_OK)
async def live(macaddress: str, timestart: str, timeend: str, db: db_dependency, request: Request):
    record = db.query(Record).filter(Record.macaddress==macaddress, Record.timestart==timestart, Record.timeend==timeend).first()
    if record is None:
        raise HTTPException(status_code=404, detail="Device not found")
    uri = record.storage

    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    pcs.add(pc)

    player = MediaPlayer(record.storage)
    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        print("Connection state is %s" % pc.connectionState)
        if pc.connectionState == "failed":
            await pc.close()
            pcs.discard(pc)

    pc.addTrack(player.video)

    await pc.setRemoteDescription(offer)

    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return JSONResponse(
        {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
    )


# shut down
@app.on_event("shutdown")
async def on_shutdown():
    # close peer connections
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)

