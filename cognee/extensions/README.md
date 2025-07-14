Hard condition：
- job type
- location
- is remote


Recall condition:
- target positions
- core skill


Attributes fields involved in the calculation of recommendation results:

job level (Senior, Mid, Junior)
job title 

work exp
- relevant experience (3 years of experience in audio and video encoding, 2 years of experience with the Flask framework)
- years of experience（5 years +）

skill
- core
- soft

industry exp （Financial industry）

educations
- degree
- major


recommendation results of weight formula(multiply all fields):

job level(0|1)

job title(0|1)

work exp [0.4] 
- relevant experience (0.3)
- years of experience（0.1）

skill [0.3] 

industry exp [0.1]

educations [0.2] 
- degree(0.1)
- major(0.1)