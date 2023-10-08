// webrtc
var pc = null;

function negotiate(id) {
    pc.addTransceiver('video', {direction: 'recvonly'});
    return pc.createOffer().then(function(offer) {
        return pc.setLocalDescription(offer);
    }).then(function() {
        // wait for ICE gathering to complete
        return new Promise(function(resolve) {
            if (pc.iceGatheringState === 'complete') {
                resolve();
            } else {
                function checkState() {
                    if (pc.iceGatheringState === 'complete') {
                        pc.removeEventListener('icegatheringstatechange', checkState);
                        resolve();
                    }
                }
                pc.addEventListener('icegatheringstatechange', checkState);
            }
        });
    }).then(function() {
        var offer = pc.localDescription;
        var input = document.getElementById(id);
        var userId = input.value;

        return fetch(`/devices/live/${userId}`, {
            body: JSON.stringify({
                sdp: offer.sdp,
                type: offer.type,
            }),
            headers: {
                'Content-Type': 'application/json'
            },
            method: 'POST'
        });
    }).then(function(response) {
        return response.json();
    }).then(function(answer) {
        return pc.setRemoteDescription(answer);
    }).catch(function(e) {
        alert(e);
    });
}

function start() {
    var config = {
        sdpSemantics: 'unified-plan'
    };

    config.iceServers = [{urls: ['stun:stun.l.google.com:19302']}];

    pc = new RTCPeerConnection(config);

    // connect audio / video
    pc.addEventListener('track', function(evt) {
        document.getElementById('video').srcObject = evt.streams[0];
    });

    document.getElementById('start').style.display = 'none';
    negotiate('ip-live');
    document.getElementById('stop').style.display = 'inline-block';
}

function stop() {
    document.getElementById('stop').style.display = 'none';
    
    // close peer connection
    setTimeout(function() {
        pc.close();
    }, 500);

    document.getElementById('start').style.display = 'inline-block';
}

// scan

function scan(){
    fetch("/devices/scan")
    .then(function(response) {
        return response.json();
    })
    .then(function(list){
        document.getElementById('list-device').textContent = JSON.stringify(list, null, 2);
    })
    .catch(function(e){
        alert(e);
    });
}

// ############################################################# test 1 ######################################################################################
var pcs = []
// hàm chung cho kết nối đến server
function negotiateAll(ipaddress, pc) {
    pc.addTransceiver('video', {direction: 'recvonly'});
    return pc.createOffer().then(function(offer) {
        return pc.setLocalDescription(offer);
    }).then(function() {
        // wait for ICE gathering to complete
        return new Promise(function(resolve) {
            if (pc.iceGatheringState === 'complete') {
                resolve();
            } else {
                function checkState() {
                    if (pc.iceGatheringState === 'complete') {
                        pc.removeEventListener('icegatheringstatechange', checkState);
                        resolve();
                    }
                }
                pc.addEventListener('icegatheringstatechange', checkState);
            }
        });
    }).then(function() {
        var offer = pc.localDescription;

        return fetch(`/devices/live/${ipaddress}`, {
            body: JSON.stringify({
                sdp: offer.sdp,
                type: offer.type,
            }),
            headers: {
                'Content-Type': 'application/json'
            },
            method: 'POST'
        });
    }).then(function(response) {
        return response.json();
    }).then(function(answer) {
        return pc.setRemoteDescription(answer);
    }).catch(function(e) {
        alert(e);
    });
}

var list_camera = []

function connectAll(){
    // lấy thông tin tấT cả các thiết bị để tạo bảng
    fetch('/devices/scan')
    .then(function(response) {
        return response.json();
    })
    .then(function(list_cam){
        for(var i=0;i<list_cam.length;i++){
            fetch(`/devices/get/${list_cam[i].ipaddress}`)
            .then(function(response) {
                return response.json();
            })
            .then(function(device){
                list_camera.push(device);
            })
        }
        return list_camera
    })
    .then(function(){
        // Lấy thẻ tbody của bảng
        var tableBody = document.getElementById("list-camera");
        
        // Tạo 10 dòng bằng vòng lặp
        for (var i = 0; i < list_camera.length; i++) {
            // Tạo một dòng mới
            var row = document.createElement("tr");
            
            // Tạo các ô dữ liệu trong dòng
            var cell = document.createElement("td");
            var video = document.createElement("video");
            video.id = 'camera' + i.toString();
            video.controls = true;
            var h3 = document.createElement('h3')
            h3.textContent = list_camera[i].name
            cell.appendChild(h3)
            cell.appendChild(video);
            // them o vao dong
            row.appendChild(cell);

            // Thêm dòng vào tbody
            tableBody.appendChild(row);
        }
    })
    .then(function(){
        console.log(list_camera)
        // tạo kết nối đến tất cả các camera
        for(var i=0; i<list_camera.length; i++){  
            return new Promise(function(){
                var config = {
                    sdpSemantics: 'unified-plan'
                };
    
                config.iceServers = [{urls: ['stun:stun.l.google.com:19302']}];
                var pc = new RTCPeerConnection(config);
                pcs.push(pc)
                // connect audio / video
                pcs[pcs.length-1].addEventListener('track', function(evt) {
                    if(evt.streams[0]!==null)
                        document.getElementById('camera' + i.toString()).srcObject = evt.streams[0];
                });

                document.getElementById('connect-all').style.display = 'none'
                negotiateAll(list_camera[i].ipaddress, pcs[pcs.length-1])
                document.getElementById('stop-all').style.display = 'inline-block'
                list_camera.splice(0, list_camera.length)
            });
        }
        console.log("123456789");
    })
console.log('thoat ham')
}

function stopAll(){
    document.getElementById('stop-all').style.display = 'none'
    for(var i=0; i<pcs.length; i++){
        // close peer connection
            pcs[i].close();    
    }

    document.getElementById('connect-all').style.display = 'inline-block'
}
// ######################################################### test 2 ##################################################################################
// negotiate chung cho cac device
function negotiates(id, pc) {
    pc.addTransceiver('video', {direction: 'recvonly'});
    return pc.createOffer().then(function(offer) {
        return pc.setLocalDescription(offer);
    }).then(function() {
        // wait for ICE gathering to complete
        return new Promise(function(resolve) {
            if (pc.iceGatheringState === 'complete') {
                resolve();
            } else {
                function checkState() {
                    if (pc.iceGatheringState === 'complete') {
                        pc.removeEventListener('icegatheringstatechange', checkState);
                        resolve();
                    }
                }
                pc.addEventListener('icegatheringstatechange', checkState);
            }
        });
    }).then(function() {
        var offer = pc.localDescription;
        var input = document.getElementById(id);
        var userIp = input.value;

        return fetch(`/devices/live/${userIp}`, {
            body: JSON.stringify({
                sdp: offer.sdp,
                type: offer.type,
            }),
            headers: {
                'Content-Type': 'application/json'
            },
            method: 'POST'
        });
    }).then(function(response) {
        return response.json();
    }).then(function(answer) {
        return pc.setRemoteDescription(answer);
    }).catch(function(e) {
        alert(e);
    });
}
// start ip device 1
var pc1 = null
function start_one() {
    var config = {
        sdpSemantics: 'unified-plan'
    };

    config.iceServers = [{urls: ['stun:stun.l.google.com:19302']}];

    pc1 = new RTCPeerConnection(config);

    // connect audio / video
    pc1.addEventListener('track', function(evt) {
        document.getElementById('video').srcObject = evt.streams[0];
    });

    document.getElementById('start1').style.display = 'none';
    negotiates('ip-live', pc1);
    document.getElementById('stop1').style.display = 'inline-block';
}

function stop_one() {
    document.getElementById('stop1').style.display = 'none';
    
    // close peer connection
    setTimeout(function() {
        pc1.close();
    }, 500);

    document.getElementById('start1').style.display = 'inline-block';
}

// start ip live 2
var pc2 = null
function start_two() {
    var config = {
        sdpSemantics: 'unified-plan'
    };

    config.iceServers = [{urls: ['stun:stun.l.google.com:19302']}];

    pc2 = new RTCPeerConnection(config);

    // connect audio / video
    pc2.addEventListener('track', function(evt) {
        document.getElementById('video2').srcObject = evt.streams[0];
    });

    document.getElementById('start2').style.display = 'none';
    negotiates('ip-live-2', pc2);
    document.getElementById('stop2').style.display = 'inline-block';
}

function stop_two() {
    document.getElementById('stop2').style.display = 'none';
    
    // close peer connection
    setTimeout(function() {
        pc2.close();
    }, 500);

    document.getElementById('start2').style.display = 'inline-block';
}

// start ip live 3
var pc3 = null
function start_three() {
    var config = {
        sdpSemantics: 'unified-plan'
    };

    config.iceServers = [{urls: ['stun:stun.l.google.com:19302']}];

    pc3 = new RTCPeerConnection(config);

    // connect audio / video
    pc3.addEventListener('track', function(evt) {
        document.getElementById('video3').srcObject = evt.streams[0];
    });

    document.getElementById('start3').style.display = 'none';
    negotiates('ip-live-3', pc3);
    document.getElementById('stop3').style.display = 'inline-block';
}

function stop_three() {
    document.getElementById('stop3').style.display = 'none';
    
    // close peer connection
    setTimeout(function() {
        pc3.close();
    }, 500);

    document.getElementById('start3').style.display = 'inline-block';
}

// start ip device 4
var pc4 = null
function start_four() {
    var config = {
        sdpSemantics: 'unified-plan'
    };

    config.iceServers = [{urls: ['stun:stun.l.google.com:19302']}];

    pc4 = new RTCPeerConnection(config);

    // connect audio / video
    pc4.addEventListener('track', function(evt) {
        document.getElementById('video4').srcObject = evt.streams[0];
    });

    document.getElementById('start4').style.display = 'none';
    negotiates('ip-live-4', pc4);
    document.getElementById('stop4').style.display = 'inline-block';
}

function stop_four() {
    document.getElementById('stop4').style.display = 'none';
    
    // close peer connection
    setTimeout(function() {
        pc4.close();
    }, 500);

    document.getElementById('start4').style.display = 'inline-block';
}

// start play record
function negotiates_record(pc) {
    pc.addTransceiver('video', {direction: 'recvonly'});
    return pc.createOffer().then(function(offer) {
        return pc.setLocalDescription(offer);
    }).then(function() {
        // wait for ICE gathering to complete
        return new Promise(function(resolve) {
            if (pc.iceGatheringState === 'complete') {
                resolve();
            } else {
                function checkState() {
                    if (pc.iceGatheringState === 'complete') {
                        pc.removeEventListener('icegatheringstatechange', checkState);
                        resolve();
                    }
                }
                pc.addEventListener('icegatheringstatechange', checkState);
            }
        });
    }).then(function() {
        var offer = pc.localDescription;
        var mac = document.getElementById('macaddress');
        var start = document.getElementById('timestart')
        var end = document.getElementById('timeend')
        var macaddress = mac.value;
        var timestart = start.value
        var timesend = end.value

        return fetch(`/records/live/${macaddress}/${timestart}/${timesend}`, {
            body: JSON.stringify({
                sdp: offer.sdp,
                type: offer.type,
            }),
            headers: {
                'Content-Type': 'application/json'
            },
            method: 'POST'
        });
    }).then(function(response) {
        return response.json();
    }).then(function(answer) {
        return pc.setRemoteDescription(answer);
    }).catch(function(e) {
        alert(e);
    });
}

// ################################ test record stream ####################################
var pc5 = null
function start_record() {
    var config = {
        sdpSemantics: 'unified-plan'
    };

    config.iceServers = [{urls: ['stun:stun.l.google.com:19302']}];

    pc5 = new RTCPeerConnection(config);

    // connect audio / video
    pc5.addEventListener('track', function(evt) {
        document.getElementById('record').srcObject = evt.streams[0];
    });

    document.getElementById('start5').style.display = 'none';
    negotiates_record(pc5);
    document.getElementById('stop5').style.display = 'inline-block';
}

function stop_record() {
    document.getElementById('stop5').style.display = 'none';
    
    // close peer connection
    setTimeout(function() {
        pc5.close();
    }, 500);

    document.getElementById('start5').style.display = 'inline-block';
}
