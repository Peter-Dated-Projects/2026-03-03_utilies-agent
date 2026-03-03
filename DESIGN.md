# Design Logs / Thought Process while working on this project

## SEN-5_connect-everything

So I finally got the downloading system to work.
Joining everything together will be super easy.



## SEN-4_website-interaction

so i sent gemini a bunch of information regarding the ids of specific buttons and such.

i guess no i shall send it into antigravity to figure out how to implement it quickly using playwrite i think? 
question: why not Selenium?

because it doesn't matter what i pick. ai will make it easy enough to use.

Will update later when finished implementing base.

### UPDATE 1

Forgot to say, in SEN-3 i stopped the bot from being able to send emails back. i want to be able to not spam myself

### UPDATE 2

So I spun up 2 agents. One is currently updating the email validity detection system
- if we find a matter ID in either subject line or content, the email is valid.
- if we don't find a category, request clarification
- else, the category exists and we can proceed

The other agent is currently working on the website interaction

We're using playwrite, but now i'm wondering if simply using bs4 and requests would've been easier...

But then again, playwrite lets me see what he agent is doing. im sure there's an option to hide hte browser as well so.

It's been 90minutes since I started.


### UPDATE 3

I dislike how the website has us clikc a button, only for us to click another button. 
Kinda weird.

It's been 1 hour and 41 minutes. GG

### UPDATE 4

I gotta scroll, but scrolling is broken.
so i gotta zoom out. iw ill now zoom out like crazy so 10 docs are always visible.


## Sen-3_email-filtering

I'm wondering if I should just write a non LLM dependent approach...

but this would require the users to input a very specific subset of text. Which might be a bit annoying.

I think that might be better than not doing anything. Generally, I believe first we should respond to the email the user sent originally with some kinda
acknowledgment... but I'm thinking that might be too much extra... bloat?

I'll leave it as a:
- user sends request
- agent does research
- agent sends zip file
- done

and I'm considering using QWEN api for this just because I like the flexibiltiy behind agents more than simply having to 
get the user to hard write specific phrases.

Although that is most likely the easiest way to do this...

OK. here's what we can do.

For starters, i'll make it hard coded.
If i end up having too much time I'll setup qwen cuz i'm gonna have to figure out how to use it anyways.

I've decided.

*If the email subject and content don't include a MXXXXX or M-XXXXX sequence for the matter ID, we ignore it*
NO exceptions. 

### Update #1

I've concluded we don't need LLMs for this. i did end up setting up QWEN 3.5 stuff tho so now i can use it for my other projects