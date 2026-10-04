# Deferred local speech experiment — 2026-10-03

**Historical evidence only. The operator deferred local Whisper; neither Whisper nor Piper belongs to the active FCC backup.** Their deployments are stopped, with existing caches preserved. Do not restore them as part of FCC recovery. The current architecture is described in [FCC backup and switching](fcc-voice-backup.md).

The experiment used resident multilingual Whisper base-int8 weights with float32 compute and Russian Piper Irina. A generated 2.519-second phrase was transcribed exactly, but warm synthesis took 25.094 seconds and recognition took 137.945 seconds. The first base decode took about 139.3 seconds; earlier Small runs exceeded a 90-second deadline. These are local speech timings, not cloud FCC timings.

A complete synthetic Assist question, “Почему лёд плавает в воде?”, finished STT at 136.354 seconds but misrecognized “лёд” as “лет”. FCC conversation then took 8.682 seconds. HA returned a TTS URL at 145.038 seconds; first answer audio arrived at 192.427 seconds and complete audio at 221.019 seconds. The test used a 300-second deadline without changing production deadlines and did not play audio on household devices. This was never accepted for interactive voice.

A read-only audit found about 94.7% guest CPU utilization, CPU pressure 69–74% and load around 60 on 16 vCPUs. Batch encoding/provisioning were active; ancestor CPU quotas were unlimited and accumulated speech-container throttling was under two seconds. The worker lacks AVX2/FMA. These observations establish contention, not a complete explanation of every slow request. Physical-host limits were unverified. No unrelated workload was paused or moved.

The prior implementation is preserved in Git at commit `750a12614791dc4a41ca213516895a91efe4cf97`; its speech manifest is not part of the current deployment. Existing PVCs should be kept until the operator explicitly requests their removal. No further local-speech tuning is planned.
