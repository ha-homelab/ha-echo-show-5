// Offline compatibility oracle. All words and nonces here are public test fixtures.
// Run: go run integrations/vaca-nearest/src/test/golden_vectors.go > .../golden-vectors.txt
package main

import (
 "crypto/hmac"
 "crypto/pbkdf2"
 "crypto/sha256"
 "encoding/hex"
 "fmt"
 "math"
 "sort"
 "strings"
)

func signed(key []byte, value string) string {
 h := hmac.New(sha256.New, key); h.Write([]byte(value)); return hex.EncodeToString(h.Sum(nil))
}

func vector(name, word, recipient, body string) {
 key, err := pbkdf2.Key(sha256.New, word, []byte("techo5-nearest v2"), 100000, 32); if err != nil { panic(err) }
 nonce := "000102030405060708090a0b"; ts := "1793293200"
 sum := sha256.Sum256([]byte(body))
 signature := signed(key, "v2\n"+ts+"\n"+nonce+"\n"+strings.ToLower(recipient)+"\n"+hex.EncodeToString(sum[:])+"\n")
 fmt.Printf("%s.body=%x\n", name, body)
 fmt.Printf("%s.header=v2 %s %s %s\n", name, ts, nonce, signature)
 fmt.Printf("%s.proof=%s\n", name, signed(key,"answered\n"+nonce+"\nshow-office\n"+strings.ToLower(recipient)+"\n"))
}

func scoreVector() {
 // Standalone implementation of the published DSP equations, using Go float32 just like the source.
 var low [3]float32; var high, floor float32; var sum float64; var blocks [20]float32
 var position, count int; var state uint32 = 1
 lp := float32(1-math.Exp(-2*math.Pi*900/16000)); hp := float32(1-math.Exp(-2*math.Pi*200/16000))
 down := float32(1-math.Exp(-.02/.2)); up := float32(1-math.Exp(-.02/60))
 values := make([]string,0,50)
 for frame:=0; frame<250; frame++ {
  var energy float64
  for i:=0;i<320;i++ {
   n:=frame*320+i; state=state*1664525+1013904223
   sample:=int16(int(state>>24)%41-20)
   if n>=32000 && n<40000 { if n%32<16 { sample+=4000 } else { sample-=4000 } }
   x:=float32(sample)
   for p:=range low { low[p]+=(x-low[p])*lp; x=low[p] }
   high+=(x-high)*hp; x-=high; energy+=float64(x)*float64(x)
  }
  mean:=energy/320; rms:=float32(math.Sqrt(mean))
  if floor==0 { floor=max(rms,16) }; rate:=up; if rms<floor { rate=down }; floor=max(floor+(rms-floor)*rate,16)
  sum+=mean
  if (frame+1)%5==0 {
   var score float32; root:=math.Sqrt(sum/5); if root>float64(floor) { score=float32(min(20*math.Log10(root/float64(floor)),90)) }
   blocks[position]=score; position=(position+1)%20; count=min(count+1,20); sum=0
   var best float32; for j:=1;j<=min(count,12);j++ { best=max(best,blocks[(position-j+20)%20]) }
   values=append(values,fmt.Sprintf("%.9g",best))
  }
 }
 fmt.Printf("score.timeline=%s\n",strings.Join(values,","))
}

// Independent deterministic native-style election model, with an event queue in place of HTTP.
// This is a model test: it sends nothing and says nothing about the real LAN's packet loss.
func fourVector(label string, starts []int, scores []float64, partition bool) {
 type event struct { at, kind, to, from int }
 type heard struct { at, from int }
 names:=[]string{"dot-a","dot-b","show-a","show-b"}
 events:=[]event{}; observed:=[4][]heard{}; active:=[4]bool{}; answered:=[4]bool{}; elsewhere:=[4]bool{}
 results:=[]string{"","","",""}
 for i:=0;i<4;i++ {
  events=append(events,event{starts[i],0,i,i},event{starts[i]+300,3,i,i})
  if !partition { for j:=0;j<4;j++ { if i!=j { events=append(events,event{starts[i]+20,1,j,i}) } } }
 }
 for len(events)>0 {
  sort.SliceStable(events,func(i,j int)bool{if events[i].at!=events[j].at{return events[i].at<events[j].at};return events[i].kind<events[j].kind})
  e:=events[0]; events=events[1:]
  switch e.kind {
  case 0: active[e.to]=true
  case 1:
   observed[e.to]=append(observed[e.to],heard{e.at,e.from})
   if active[e.to]&&answered[e.to]&&e.at-starts[e.to]<=600 { events=append(events,event{e.at+20,2,e.from,e.to}) }
  case 2: elsewhere[e.to]=true
  case 3:
   beaten:=false
   for _,h:=range observed[e.to] { if h.at>=starts[e.to]-300 && (scores[h.from]>scores[e.to] || scores[h.from]==scores[e.to]&&names[h.from]<names[e.to]) { beaten=true } }
   answered[e.to]=!beaten&&!elsewhere[e.to]
   if answered[e.to] { results[e.to]="START" } else { results[e.to]="YIELD" }
  }
 }
 fmt.Printf("four.%s=%s\n",label,strings.Join(results,","))
}

func main() {
 vector("ascii","offline-example-house-word","Echo-Kitchen",`{"from":"show-office","turn":"0123456789abcdef","word":"privet_myshka_dab4a660248f_cal","score":25.5}`)
 vector("unicode","Пример слова дома 🔑 offline","İSTANBUL-Σ",` { "score":25.5, "word":"Привет, Мышка", "turn":"0123456789abcdef", "from":"show-office" } `)
 scoreVector()
 for i:=0;i<4;i++ { scores:=[]float64{30,30,30,30}; scores[i]=60; fourVector(fmt.Sprintf("winner%d",i),[]int{1000,1000,1000,1000},scores,false) }
 fourVector("tie",[]int{1000,1000,1000,1000},[]float64{40,40,40,40},false)
 fourVector("delayed",[]int{1000,1040,1100,1150},[]float64{20,50,30,25},false)
 fourVector("already",[]int{1000,1420,1440,1460},[]float64{10,90,80,70},false)
 fourVector("partition",[]int{1000,1000,1000,1000},[]float64{10,90,80,70},true)
}
