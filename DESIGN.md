# Design Logs / Thought Process while working on this project


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