#!/usr/bin/env python3
# Fetched from http://nirmalpatel.com/fcgi/hn.py
# Updated to python3 by Lars Ingebrigtsen

"""
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

apt install python3-uritools python3-feedparser python3-furl python3-bs4

"""

import urllib, re, os, sys, html, feedparser
from xml.sax.saxutils import escape
from bs4 import BeautifulSoup
from pprint import pprint

HN_RSS_FEED = "https://news.ycombinator.com/rss"

NEGATIVE    = re.compile("comment|meta|footer|footnote|foot")
POSITIVE    = re.compile("post|hentry|entry|content|text|body|article")
PUNCTUATION = re.compile("""[!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~]""")

def grabContent(link, html):
    replaceBrs = re.compile("<br */? *>[ \r\n]*<br */? *>")
    html = re.sub(replaceBrs, "</p><p>", html)
    
    try:
        soup = BeautifulSoup(html, features="lxml")
    except html.parser.HTMLParseError:
        return ""
    
    # REMOVE SCRIPTS
    for s in soup.find_all("script"):
        s.extract()
    
    allParagraphs = soup.find_all("p")
    topParent     = None
    
    parents = []
    for paragraph in allParagraphs:
        
        parent = paragraph.parent
        
        if (parent not in parents):
            parents.append(parent)
            parent.score = 0
            
            if (parent.has_attr("class")):
                if (NEGATIVE.match(" ".join(parent["class"]))):
                    parent.score -= 50
                if (POSITIVE.match(" ".join(parent["class"]))):
                    parent.score += 25
                    
            if (parent.has_attr("id")):
                if (NEGATIVE.match(parent["id"])):
                    parent.score -= 50
                if (POSITIVE.match(parent["id"])):
                    parent.score += 25

        if (parent.score == None):
            parent.score = 0
        
        innerText = paragraph.encode_contents().decode('utf-8')
        if (len(innerText) > 10):
            parent.score += 1
            
        parent.score += innerText.count(",")
        
    for parent in parents:
        if ((not topParent) or (parent.score > topParent.score)):
            topParent = parent

    if (not topParent):
        return ""
            
    # REMOVE LINK'D STYLES
    styleLinks = soup.find_all("link", attrs={"type" : "text/css"})
    for s in styleLinks:
        s.extract()

    # REMOVE ON PAGE STYLES
    for s in soup.find_all("style"):
        s.extract()

    # CLEAN STYLES FROM ELEMENTS IN TOP PARENT
    for ele in topParent.find_all(True):
        del(ele['style'])
        del(ele['class'])
        
    killDivs(topParent)
    clean(topParent, "form")
    clean(topParent, "object")
    clean(topParent, "iframe")
    
    fixLinks(topParent, link)
    
    return topParent.encode_contents().decode('utf-8')
    

def fixLinks(parent, link):
    tags = parent.find_all(True)
    for t in tags:
        if (t.has_attr("href")):
            t["href"] = urllib.parse.urljoin(link, t["href"])
        if (t.has_attr("src")):
            t["src"] = urllib.parse.urljoin(link, t["src"])


def clean(top, tag, minWords=10000):
    tags = top.find_all(tag)
    for t in tags:
        if (t.encode_contents().decode('utf-8').count(" ") < minWords):
            t.extract()


def killDivs(parent):
    divs = parent.find_all("div")
    for d in divs:
        p     = len(d.find_all("p"))
        img   = len(d.find_all("img"))
        li    = len(d.find_all("li"))
        a     = len(d.find_all("a"))
        embed = len(d.find_all("embed"))
        pre   = len(d.find_all("pre"))
        code  = len(d.find_all("code"))
    
        if (d.encode_contents().decode('utf-8').count(",") < 10):
            if ((pre == 0) and (code == 0)):
                if ((img > p ) or (li > p) or (a > p) or (p == 0) or (embed > 0)):
                    d.extract()
    

def upgradeLink(link):
    if (not (link.startswith('https://news.ycombinator.com') or link.endswith('.pdf'))):
        linkFile = "upgraded/" + re.sub(PUNCTUATION, "_", link)
        if (os.path.exists(linkFile)):
            return open(linkFile).read()
        else:
            content = ""
            try:
                html = urllib.request.urlopen(link).read()
                try:
                    html = html.decode('utf-8')
                except UnicodeDecodeError:
                    html = ""
                content = grabContent(link, html)
                filp = open(linkFile, "w")
                filp.write(content)
                filp.close()
            except IOError:
                pass
            return content
    else:
        return ""


def upgradeFeed(feedUrl):
    feedData = urllib.request.urlopen(feedUrl).read()
    
    upgradedLinks = []
    parsedFeed = feedparser.parse(feedData)
    
    for entry in parsedFeed.entries:
        upgradedLinks.append((entry, upgradeLink(entry.link)))
        
    rss = """<rss version="2.0">
<channel>
	<title>Hacker News</title>
	<link>https://news.ycombinator.com/</link>
	<description>Items from HackerNews.</description>
	
    """

    for entry, content in upgradedLinks:
        content = content.replace("]]>", "")
        rss += u"""
    <item>
        <title>%s</title>
        <link>%s</link>
        <comments>%s</comments>
        <description>
            <![CDATA[<a href="%s">Comments</a><br/>%s<br/><a href="%s">Comments</a>]]>
        </description>
    </item>
""" % (entry.title, escape(entry.link), escape(entry.comments), entry.comments, content, entry.comments)

    rss += """
</channel>
</rss>"""

    return rss


if __name__ == "__main__":
    sys.stdout.buffer.write(upgradeFeed(HN_RSS_FEED).encode('utf-8'))
