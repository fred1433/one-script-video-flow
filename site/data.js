window.RUN = {
 "project": "DEMO-001",
 "status": "Ready to upload",
 "master": {
  "src": "media/DEMO-001_master_v01.mp4",
  "file": "DEMO-001_master_v01.mp4",
  "poster": "media/poster_master.jpg",
  "duration": 72.0,
  "w": 1920,
  "h": 1080,
  "mb": 11.4
 },
 "scenes": [
  {
   "id": "A",
   "title": "The part",
   "start": 0.0,
   "end": 13.0,
   "short": null
  },
  {
   "id": "B",
   "title": "Lug and groove",
   "start": 13.0,
   "end": 29.0,
   "short": 1
  },
  {
   "id": "C",
   "title": "The quarter turn",
   "start": 29.0,
   "end": 45.0,
   "short": 2
  },
  {
   "id": "D",
   "title": "The section",
   "start": 45.0,
   "end": 64.0,
   "short": 3
  },
  {
   "id": "E",
   "title": "Close",
   "start": 64.0,
   "end": 72.0,
   "short": null
  }
 ],
 "lines": [
  {
   "id": "L01",
   "text": "This is a cartridge lock. A fictional one, built for this demo.",
   "start": 0.8,
   "end": 5.225,
   "scene": "A"
  },
  {
   "id": "L02",
   "text": "Its whole job is to hold a cartridge in place, with one movement anyone can learn.",
   "start": 6.4,
   "end": 12.125,
   "scene": "A"
  },
  {
   "id": "L03",
   "text": "The cartridge carries a single lug on its side.",
   "start": 13.5,
   "end": 17.0,
   "scene": "B"
  },
  {
   "id": "L04",
   "text": "Line it up with the open groove in the housing, and the lug guides it straight down.",
   "start": 17.4,
   "end": 22.6,
   "scene": "B"
  },
  {
   "id": "L05",
   "text": "There is only one way in, so it cannot go in crooked.",
   "start": 23.2,
   "end": 27.0,
   "scene": "B"
  },
  {
   "id": "L06",
   "text": "At the bottom of the groove, a quarter turn carries the lug sideways.",
   "start": 29.6,
   "end": 34.15,
   "scene": "C"
  },
  {
   "id": "L07",
   "text": "At the end of the turn, a spring lifts it into a notch, behind the amber stop.",
   "start": 34.8,
   "end": 39.925,
   "scene": "C"
  },
  {
   "id": "L08",
   "text": "You hear it as one click.",
   "start": 40.6,
   "end": 42.975,
   "scene": "C"
  },
  {
   "id": "L09",
   "text": "Cut the housing in half, and you can see why it holds.",
   "start": 45.6,
   "end": 49.45,
   "scene": "D"
  },
  {
   "id": "L10",
   "text": "The spring keeps pushing the cartridge up, so the lug stays pressed against the stop.",
   "start": 50.2,
   "end": 55.575,
   "scene": "D"
  },
  {
   "id": "L11",
   "text": "Pull on it, and nothing moves. To release it, you push down, and turn back.",
   "start": 56.4,
   "end": 61.4,
   "scene": "D"
  },
  {
   "id": "L12",
   "text": "One lug. One groove. One quarter turn.",
   "start": 65.0,
   "end": 68.35,
   "scene": "E"
  }
 ],
 "shorts": [
  {
   "index": 1,
   "scene": "B",
   "hook": "Why it only goes in one way",
   "start": 13.0,
   "versions": [
    {
     "v": 1,
     "file": "DEMO-001_S01_vertical_v01.mp4",
     "src": "media/DEMO-001_S01_vertical_v01.mp4",
     "poster": "media/poster_S01_v01.jpg",
     "duration": 18.0,
     "w": 1080,
     "h": 1920,
     "mb": 2.9
    }
   ]
  },
  {
   "index": 2,
   "scene": "C",
   "hook": "A quarter turn, then one click",
   "start": 29.0,
   "versions": [
    {
     "v": 1,
     "file": "DEMO-001_S02_vertical_v01.mp4",
     "src": "media/DEMO-001_S02_vertical_v01.mp4",
     "poster": "media/poster_S02_v01.jpg",
     "duration": 18.0,
     "w": 1080,
     "h": 1920,
     "mb": 3.0
    },
    {
     "v": 2,
     "file": "DEMO-001_S02_vertical_v02.mp4",
     "src": "media/DEMO-001_S02_vertical_v02.mp4",
     "poster": "media/poster_S02_v02.jpg",
     "duration": 18.0,
     "w": 1080,
     "h": 1920,
     "mb": 3.1
    }
   ]
  },
  {
   "index": 3,
   "scene": "D",
   "hook": "Why pulling does nothing",
   "start": 45.0,
   "versions": [
    {
     "v": 1,
     "file": "DEMO-001_S03_vertical_v01.mp4",
     "src": "media/DEMO-001_S03_vertical_v01.mp4",
     "poster": "media/poster_S03_v01.jpg",
     "duration": 21.0,
     "w": 1080,
     "h": 1920,
     "mb": 2.7
    }
   ]
  }
 ],
 "events": [
  {
   "event": "approved",
   "stage": "script",
   "label": "Script approved",
   "role": "Producer",
   "actor": "builder (for this demo)",
   "files": [
    "script/DEMO-001_script.md"
   ],
   "note": null,
   "shorts": null,
   "detail": {
    "script_sha1": "06628d5d0f2e",
    "lines": 12
   },
   "time": {
    "iso": "2026-11-07T14:28:23+00:00",
    "hm": "14:28",
    "day": "7 Nov 2026"
   }
  },
  {
   "event": "delivered",
   "stage": "voice",
   "label": "Voice-over",
   "role": "Voice-over (local model)",
   "actor": "render service",
   "files": [
    "voice/DEMO-001_vo_L01_v01.wav",
    "voice/DEMO-001_vo_L02_v01.wav",
    "voice/DEMO-001_vo_L03_v01.wav",
    "voice/DEMO-001_vo_L04_v01.wav",
    "voice/DEMO-001_vo_L05_v01.wav",
    "voice/DEMO-001_vo_L06_v01.wav",
    "voice/DEMO-001_vo_L07_v01.wav",
    "voice/DEMO-001_vo_L08_v01.wav",
    "voice/DEMO-001_vo_L09_v01.wav",
    "voice/DEMO-001_vo_L10_v01.wav",
    "voice/DEMO-001_vo_L11_v01.wav",
    "voice/DEMO-001_vo_L12_v01.wav"
   ],
   "note": null,
   "shorts": null,
   "detail": {
    "changed_lines": [],
    "script_sha1": "06628d5d0f2e",
    "voice": "kokoro bf_emma",
    "seconds": 10.7
   },
   "time": {
    "iso": "2026-11-07T14:28:34+00:00",
    "hm": "14:28",
    "day": "7 Nov 2026"
   }
  },
  {
   "event": "delivered",
   "stage": "storyboard",
   "label": "Storyboard",
   "role": "Storyboard & Camera Director",
   "actor": "render service",
   "files": [
    "DEMO-001_storyboard_v01.json",
    "DEMO-001_storyboard_v01.png"
   ],
   "note": null,
   "shorts": null,
   "detail": {
    "version": 1,
    "warnings": [],
    "duration": 72.0,
    "seconds": 24.5
   },
   "time": {
    "iso": "2026-11-07T14:28:58+00:00",
    "hm": "14:28",
    "day": "7 Nov 2026"
   }
  },
  {
   "event": "awaiting",
   "stage": "storyboard",
   "label": "Storyboard",
   "role": "Storyboard & Camera Director",
   "actor": null,
   "files": [
    "DEMO-001_storyboard_v01.json",
    "DEMO-001_storyboard_v01.png"
   ],
   "note": null,
   "shorts": null,
   "detail": null,
   "time": {
    "iso": "2026-11-07T14:28:59+00:00",
    "hm": "14:28",
    "day": "7 Nov 2026"
   }
  },
  {
   "event": "approved",
   "stage": "storyboard",
   "label": "Storyboard",
   "role": "Storyboard & Camera Director",
   "actor": "builder (for this demo)",
   "files": [
    "DEMO-001_storyboard_v01.json",
    "DEMO-001_storyboard_v01.png"
   ],
   "note": "looks right",
   "shorts": null,
   "detail": null,
   "time": {
    "iso": "2026-11-07T14:28:59+00:00",
    "hm": "14:28",
    "day": "7 Nov 2026"
   }
  },
  {
   "event": "delivered",
   "stage": "look",
   "label": "Look frames",
   "role": "AI Image Artist",
   "actor": "render service",
   "files": [
    "DEMO-001_lookframes_v01.png"
   ],
   "note": null,
   "shorts": null,
   "detail": {
    "version": 1,
    "seconds": 13.1
   },
   "time": {
    "iso": "2026-11-07T14:29:12+00:00",
    "hm": "14:29",
    "day": "7 Nov 2026"
   }
  },
  {
   "event": "awaiting",
   "stage": "look",
   "label": "Look frames",
   "role": "AI Image Artist",
   "actor": null,
   "files": [
    "DEMO-001_lookframes_v01.png"
   ],
   "note": null,
   "shorts": null,
   "detail": null,
   "time": {
    "iso": "2026-11-07T14:29:12+00:00",
    "hm": "14:29",
    "day": "7 Nov 2026"
   }
  },
  {
   "event": "approved",
   "stage": "look",
   "label": "Look frames",
   "role": "AI Image Artist",
   "actor": "builder (for this demo)",
   "files": [
    "DEMO-001_lookframes_v01.png"
   ],
   "note": "looks right",
   "shorts": null,
   "detail": null,
   "time": {
    "iso": "2026-11-07T14:29:14+00:00",
    "hm": "14:29",
    "day": "7 Nov 2026"
   }
  },
  {
   "event": "delivered",
   "stage": "animate",
   "label": "Scenes rendered",
   "role": "AI Video Animator",
   "actor": "render service",
   "files": [],
   "note": null,
   "shorts": null,
   "detail": {
    "rendered": [
     "A-wide",
     "B-wide",
     "B-tall",
     "C-wide",
     "C-tall",
     "D-wide",
     "D-tall",
     "E-wide"
    ],
    "reused": [],
    "quality": "final",
    "seconds": 10893.7
   },
   "time": {
    "iso": "2026-11-07T17:30:48+00:00",
    "hm": "17:30",
    "day": "7 Nov 2026"
   }
  },
  {
   "event": "delivered",
   "stage": "master",
   "label": "Master edit",
   "role": "AI Video Animator",
   "actor": "render service",
   "files": [
    "DEMO-001_master_v01.mp4"
   ],
   "note": null,
   "shorts": null,
   "detail": {
    "version": 1,
    "rebuilt": true,
    "seconds": 30.2
   },
   "time": {
    "iso": "2026-11-07T17:31:18+00:00",
    "hm": "17:31",
    "day": "7 Nov 2026"
   }
  },
  {
   "event": "awaiting",
   "stage": "master",
   "label": "Master edit",
   "role": "AI Video Animator",
   "actor": null,
   "files": [
    "DEMO-001_master_v01.mp4"
   ],
   "note": null,
   "shorts": null,
   "detail": null,
   "time": {
    "iso": "2026-11-07T17:31:18+00:00",
    "hm": "17:31",
    "day": "7 Nov 2026"
   }
  },
  {
   "event": "approved",
   "stage": "master",
   "label": "Master edit",
   "role": "AI Video Animator",
   "actor": "builder (for this demo)",
   "files": [
    "DEMO-001_master_v01.mp4"
   ],
   "note": "looks right",
   "shorts": null,
   "detail": null,
   "time": {
    "iso": "2026-11-07T17:31:20+00:00",
    "hm": "17:31",
    "day": "7 Nov 2026"
   }
  },
  {
   "event": "delivered",
   "stage": "shorts",
   "label": "Shorts",
   "role": "Storyboard & Camera Director",
   "actor": "render service",
   "files": [
    "DEMO-001_S01_vertical_v01.mp4",
    "DEMO-001_S02_vertical_v01.mp4",
    "DEMO-001_S03_vertical_v01.mp4"
   ],
   "note": null,
   "shorts": null,
   "detail": {
    "shorts": [
     {
      "short": 1,
      "file": "DEMO-001_S01_vertical_v01.mp4",
      "version": 1,
      "rebuilt": true
     },
     {
      "short": 2,
      "file": "DEMO-001_S02_vertical_v01.mp4",
      "version": 1,
      "rebuilt": true
     },
     {
      "short": 3,
      "file": "DEMO-001_S03_vertical_v01.mp4",
      "version": 1,
      "rebuilt": true
     }
    ],
    "seconds": 22.2
   },
   "time": {
    "iso": "2026-11-07T17:31:43+00:00",
    "hm": "17:31",
    "day": "7 Nov 2026"
   }
  },
  {
   "event": "awaiting",
   "stage": "shorts",
   "label": "Shorts",
   "role": "Storyboard & Camera Director",
   "actor": null,
   "files": [
    "DEMO-001_S01_vertical_v01.mp4",
    "DEMO-001_S02_vertical_v01.mp4",
    "DEMO-001_S03_vertical_v01.mp4"
   ],
   "note": null,
   "shorts": null,
   "detail": null,
   "time": {
    "iso": "2026-11-07T17:31:43+00:00",
    "hm": "17:31",
    "day": "7 Nov 2026"
   }
  },
  {
   "event": "changes",
   "stage": "shorts",
   "label": "Shorts",
   "role": "Storyboard & Camera Director",
   "actor": "builder (for this demo)",
   "files": [
    "DEMO-001_S01_vertical_v01.mp4",
    "DEMO-001_S02_vertical_v01.mp4",
    "DEMO-001_S03_vertical_v01.mp4"
   ],
   "note": "The caption covers the lug",
   "shorts": {
    "1": "approved",
    "3": "approved",
    "2": {
     "rejected": "The caption covers the lug",
     "fix": {
      "caption_pos": "lower"
     }
    }
   },
   "detail": null,
   "time": {
    "iso": "2026-11-07T17:31:45+00:00",
    "hm": "17:31",
    "day": "7 Nov 2026"
   }
  },
  {
   "event": "delivered",
   "stage": "shorts",
   "label": "Shorts",
   "role": "Storyboard & Camera Director",
   "actor": "render service",
   "files": [
    "DEMO-001_S02_vertical_v02.mp4"
   ],
   "note": null,
   "shorts": null,
   "detail": {
    "shorts": [
     {
      "short": 2,
      "file": "DEMO-001_S02_vertical_v02.mp4",
      "version": 2,
      "rebuilt": true
     }
    ],
    "seconds": 6.9
   },
   "time": {
    "iso": "2026-11-07T17:31:52+00:00",
    "hm": "17:31",
    "day": "7 Nov 2026"
   }
  },
  {
   "event": "awaiting",
   "stage": "shorts",
   "label": "Shorts",
   "role": "Storyboard & Camera Director",
   "actor": null,
   "files": [
    "DEMO-001_S02_vertical_v02.mp4"
   ],
   "note": null,
   "shorts": null,
   "detail": null,
   "time": {
    "iso": "2026-11-07T17:31:52+00:00",
    "hm": "17:31",
    "day": "7 Nov 2026"
   }
  },
  {
   "event": "approved",
   "stage": "shorts",
   "label": "Shorts",
   "role": "Storyboard & Camera Director",
   "actor": "builder (for this demo)",
   "files": [
    "DEMO-001_S02_vertical_v02.mp4"
   ],
   "note": "looks right",
   "shorts": null,
   "detail": null,
   "time": {
    "iso": "2026-11-07T17:31:54+00:00",
    "hm": "17:31",
    "day": "7 Nov 2026"
   }
  },
  {
   "event": "delivered",
   "stage": "package",
   "label": "Ready to upload",
   "role": "Producer",
   "actor": "render service",
   "files": [
    "DEMO-001_package.json",
    "DEMO-001_thumbnail_v01.jpg"
   ],
   "note": null,
   "shorts": null,
   "detail": {
    "status": "Ready to upload",
    "seconds": 0.0
   },
   "time": {
    "iso": "2026-11-07T17:31:54+00:00",
    "hm": "17:31",
    "day": "7 Nov 2026"
   }
  }
 ],
 "thumbnail": "media/DEMO-001_thumbnail_v01.jpg"
};
