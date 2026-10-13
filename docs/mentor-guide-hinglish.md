# Mentor Guide (Hinglish)

Yeh repo ek lab hai, production failover platform nahi. Pehle local behavior verify karo; AWS mein kuch create karne se pehle account, permissions, region pair aur cost approve karo. Koi bhi command jo `apply` ya `destroy` chalati hai, uska Terraform plan pehle padho.

## Data flow seedhi bhaasha mein

1. EventBridge roz 02:00 UTC par Lambda ko start karta hai. Time UTC hai, local Windows timezone nahi.
2. Lambda source bucket ko paginator se pages mein padhta hai. Isliye ek page ke baad objects silently chhoot nahi jaate.
3. Har invocation ek naya recovery prefix banati hai, misaal: `recovery/20261013T020000123456Z-request-id/`. Naya prefix purana recovery point overwrite nahi karta.
4. Har object ke liye S3 copy hota hai. Destination par object ka size verify hota hai. Koi item fail hua to summary log hoti hai aur invocation error throw karti hai, jisse CloudWatch `Errors` metric/alarm kaam kar sake.
5. Restore script us ek prefix ko local folder mein download karta hai. Verify script source aur restore ke file SHA-256 hashes compare karta hai.

Empty bucket ko zero-object successful run maana jaata hai. Yeh tab sahi hai jab empty source valid ho; production mein alag alarm/guard chahiye ho sakta hai. Pagination, `copy()` aur `head_object()` ke alawa paginator-level failure bhi invocation ko fail karega aur CloudWatch mein dikhna chahiye.

## Regions aur objectives

`source_region` mein source bucket aur Lambda hain. `destination_region` mein DR bucket hai aur dono values alag honi chahiye. Regions choose karne se pehle account allow-list, data residency, latency, inter-region transfer aur dono regions mein service availability check karo. Example `us-east-1`/`us-west-2` sirf sample hai.

Daily run ka intended RPO lagbhag 24 ghante hai, lekin failure ke baad recovery point aur purana hoga. RTO ka koi promised number nahi: real sample ko restore karke stopwatch se naapna hai. Lambda ki hard runtime ceiling 15 minutes hai; oversized workload ko batches/Step Functions ya managed backup design chahiye.

## Cost ka practical matlab

- Dono buckets mein data rakhne se do regions ka storage charge hoga.
- Copy requests aur inter-region data transfer charge ho sakte hain. Har daily run naya full current copy banata hai; unchanged objects bhi dobara transfer/store hote hain.
- Lambda duration, CloudWatch log ingestion/storage/alarm metrics, aur SNS notifications bhi billable ho sakte hain.
- 14-day lifecycle chhoti lab ke liye retention control hai, instant deletion nahi. S3 lifecycle asynchronously expire karta hai.
- Isliye kuch chhoti sample files se shuru karo, alarms ka email confirm karo, drill evidence le lo, phir plan dekhkar resources destroy karo. AWS billing console mein baad mein verify karo.

## Support engineer ki investigation routine

1. Alert ka timestamp, function name, request ID aur failure count note karo.
2. Usi interval ki `/aws/lambda/<prefix>-s3-backup` log stream kholo. `backup_result` mein counts aur object failure sample dekho.
3. `AccessDenied` ko operation ke hisaab se isolate karo: `ListBucket` bucket ARN par, `GetObject` source object ARN par, `PutObject` destination recovery prefix par. SCP, bucket policy, account/region aur role trust bhi check karo.
4. Agar copied count kam ho, successful objects ko preserve karo; failure ka root cause fix karke naya run chalao. Is implementation mein retries alag unique run prefixes bana sakti hain, isliye unnecessary retry storage badha sakti hai.
5. Alarm missing ho to pehle SNS email subscription `Confirmed` hai ya nahi dekho. Alarm sirf Lambda errors dekhta hai; missed schedule ke liye production mein last-success heartbeat chahiye.
6. Restore ke waqt exact run prefix use karo. Restore ka JSON aur hash comparison save karo. Lambda success ko DR drill pass mat bolo.

## Interview: 2-minute explanation

"Maine ek chhota AWS disaster-recovery lab banaya. Terraform source region mein versioned, encrypted, public-access-blocked S3 bucket aur Python/Boto3 Lambda banata hai, aur doosre region mein independent recovery bucket. EventBridge roz Lambda invoke karta hai. Lambda S3 paginator se sab current objects padhta hai, har run ke liye unique recovery prefix banata hai, copies karta hai, copied size check karta hai, aur per-object failure count log karke invocation fail karta hai. CloudWatch log/Errors alarm aur SNS email failure signal dete hain. Recovery ke liye maine exact run prefix download karne ka local Python tool aur SHA-256 compare script banaya. Unit tests pagination, empty bucket, partial failure, hash mismatch aur unsafe restore path cover karte hain. Is lab ka 24-hour intended RPO sirf schedule-based estimate hai; measured RTO tabhi report karunga jab real AWS drill complete ho. Current limits mein full current copy har roz, Lambda 15-minute ceiling, historical source versions ka copy na hona, aur missed-run heartbeat monitoring ka future kaam hona shamil hai."

## 20 technical interview questions

1. **RPO aur RTO kya hain?** RPO acceptable data-loss window hai; RTO service/data restore ka acceptable time. Daily schedule 24-hour intended RPO dikhata hai, RTO actual timed drill ke bina claim nahi karna.
2. **S3 versioning aur cross-region backup mein farq?** Versioning ek bucket mein prior object versions bachata hai; doosre region ka recovery bucket regional/account blast radius se alag copy de sakta hai.
3. **Har backup run alag prefix kyun?** Ek recovery point ko agla run overwrite na kare. Trade-off: repeated full copies zyada storage/transfer leti hain.
4. **S3 list pagination kyun zaroori hai?** List response limited page size mein aata hai; paginator continuation tokens chala kar saare objects tak pahunchata hai.
5. **Empty bucket par expected behavior?** Zero objects, zero failures wala successful run. Agar empty bucket unexpected ho, production alarm/policy alag add karni chahiye.
6. **Partial failure kaise surface hota hai?** Successful copies count hoti hain, failed keys ka bounded sample log hota hai, phir exception Lambda `Errors` metric raise karti hai.
7. **S3 ETag SHA-256 kyun nahi?** Multipart aur encryption scenarios mein ETag MD5 bhi nahi hota. Isliye restore files ka SHA-256 locally calculate karke compare hota hai.
8. **Lambda retry duplicate kaise affect karti hai?** Retry dobara execution/copy kara sakti hai. Unique prefix purani copy ko overwrite se bachata hai, par duplicate data/cost ho sakta hai.
9. **15-minute Lambda limit ka plan?** Workload ko pages/chunks mein Step Functions, SQS workers, AWS Backup, ya S3 replication jaise managed approach par shift karna.
10. **Cross-region data transfer ka impact?** Source bytes region boundaries cross karte hain, jiske transfer aur destination storage charges ho sakte hain; data volume estimate karke test karna hai.
11. **IAM least privilege kaise lagaya?** `ListBucket` source bucket ARN, `GetObject` source objects, `PutObject` sirf destination recovery prefix, aur log actions sirf function log group par.
12. **Lambda ko public access kyun nahi?** EventBridge permission sirf scheduled rule ARN se invoke allow karti hai; S3 buckets public ACL/policy access block karte hain.
13. **KMS use karte to kya badalta?** Key policies/grants aur regional keys add karne padte; copy/decrypt/encrypt permissions aur cross-account recovery design test karna hota.
14. **CloudWatch `Errors` alarm kya miss kar sakta hai?** Schedule kabhi fire hi na ho to error metric nahi banta. Last-success timestamp/heartbeat aur missed-run alarm bhi chahiye.
15. **SNS email alert deliver kyun na ho?** Subscription pending, spam filter, wrong endpoint, topic/action permission, ya alarm insufficient data/state transition check karo.
16. **Terraform state mein kya risk hai?** Resource identifiers aur sensitive values ho sakti hain; remote encrypted access-controlled backend, locking, versioning chahiye. Is lab ne abhi local state default rakha hai aur use commit nahi karta.
17. **`plan` aur `apply` ka difference?** `plan` proposed changes preview karta hai; `apply` AWS par resources mutate/create karta hai aur charge trigger kar sakta hai.
18. **Drift kaise handle karoge?** `plan` se Terraform desired aur AWS actual compare, unauthorized change ka source investigate, review ke baad code ya resource correct karna.
19. **Lifecycle retention delete ko turant kyun nahi dikhata?** S3 lifecycle expiration asynchronous hai; versioned bucket mein current expiration delete marker bana sakta hai, noncurrent versions alag expire hote hain.
20. **Backup successful ho to DR proven hai?** Nahi. Correct run ka data alag location par restore ho, files/hashes verify hon, aur measured RTO/RPO evidence record ho tabhi drill pass hai.

## Real-world scenarios par jawab

- **Galat deploy ne source objects delete kar diye:** source versioning se past versions inspect; clean recovery point ke exact prefix se alag test bucket/folder mein restore; hash/sample checks ke baad controlled cutover.
- **Destination region temporarily unavailable:** last completed recovery point aur actual lag identify, stale-data impact business owner ko communicate, account policy ke approved alternate region/process par restore.
- **Lambda `AccessDenied`:** failed S3 API identify, assumed role aur bucket policy/SCP check, missing exact action/resource correct; `s3:*` dena solution nahi.
- **Backup 15 minutes par timeout:** object count/bytes/copy duration measure; sequential Lambda design scale ceiling maan kar partitioned workflow ya managed replication design propose.
- **SNS alert nahi mila:** alarm state/metric history, action configuration, topic policy, subscription confirmation aur email quarantine investigate; alarm ko manual test event se validate.
- **Terraform apply aadhe mein fail hua:** provider error aur AWS partial resources inspect; state/plan safe preserve, idempotent plan dubara review; state manually delete na karo.