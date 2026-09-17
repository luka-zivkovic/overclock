// Labeled customer messages for the experiments. Three binary labels per message:
//   delay:   the message says a shipment, delivery, or order is late, delayed, or has not arrived when expected
//   billing: the message concerns charges, invoices, payments, refunds, prices, or subscription cost
//   angry:   the message expresses anger, hostility, or clear frustration (disappointment alone is not enough)
// Written by hand to cover clear cases, negations, sarcasm, mixed topics, and near-misses.
export interface LabeledMessage {
  id: string;
  text: string;
  delay: boolean;
  billing: boolean;
  angry: boolean;
}

const rows: Array<[string, boolean, boolean, boolean]> = [
  ["Order #4471 was supposed to arrive Tuesday and the tracking page still says 'label created'. It's Friday.", true, false, false],
  ["Can I change the billing email on our account to finance@acme.example?", false, true, false],
  ["Your courier left the parcel at the wrong building and now it's gone. I need this resolved today.", false, false, true],
  ["Love the new dashboard, just wanted to say thanks.", false, false, false],
  ["Third week waiting on the replacement unit. Every update says 'shipping soon'. What is going on?", true, false, true],
  ["How do I export last quarter's invoices as CSV?", false, true, false],
  ["The package arrived but the box was crushed and two of the five units are cracked.", false, false, false],
  ["Shipment delayed again? The ETA moved from the 3rd to the 9th with no explanation. We have a launch on the 8th.", true, false, true],
  ["Please cancel my subscription at the end of this billing cycle.", false, true, false],
  ["Password reset emails never arrive. Checked spam.", false, false, false],
  ["Delivery was one day late but everything is fine. No action needed, just FYI.", true, false, false],
  ["Can we get a quote for 500 units with delivery before the end of the month?", false, true, false],
  ["Where is my order? It's been two weeks since the confirmation email and nothing since.", true, false, false],
  ["Requesting the SOC 2 report for our vendor review.", false, false, false],
  ["I was charged twice for the March invoice. Please refund the duplicate.", false, true, false],
  ["This is the fourth email about the double charge. Fix it or I'm disputing it with my bank.", false, true, true],
  ["Tracking shows delivered but nothing was left at the door. Neighbors haven't seen it either.", true, false, false],
  ["The order arrived a day early, nice surprise. Thanks!", false, false, false],
  ["Your pricing page says $49 but I was billed $59. Which is it?", false, true, false],
  ["Not delayed at all, arrived exactly on the date promised. Just confirming receipt.", false, false, false],
  ["Honestly, I'm done. Three broken promises on the ship date and now you want me to 'be patient'?", true, false, true],
  ["Could you resend the receipt for order 8812? My accountant needs it for expenses.", false, true, false],
  ["What's the return window on the blue model? Haven't opened it yet.", false, false, false],
  ["The invoice lists 12 seats but we only have 9 users. Please correct and rebill.", false, true, false],
  ["Still no sign of the parcel. Estimated delivery was last Monday.", true, false, false],
  ["Great support last week, Maria was fantastic. Pass it on.", false, false, false],
  ["Why does every shipment from you take three weeks when everyone else does two days? Ridiculous.", true, false, true],
  ["I'd like to upgrade to the annual plan. Do you prorate the remaining months?", false, true, false],
  ["The app logs me out every ten minutes. Started after yesterday's update.", false, false, false],
  ["Package says out for delivery since 6am, it's 9pm. Is the driver lost?", true, false, false],
  ["Do you ship to Iceland? Couldn't find it in the checkout dropdown.", false, false, false],
  ["Your 'express' shipping is a joke. Paid extra, still waiting a week later. Refund the shipping fee.", true, true, true],
  ["Please update the VAT number on our invoices to DE123456789.", false, true, false],
  ["The replacement arrived and works perfectly. Thanks for the quick turnaround.", false, false, false],
  ["I asked for a callback four days ago. Nobody called. Is anyone actually working there?", false, false, true],
  ["Can you confirm the delivery date for PO 2231? We need to schedule the installers.", false, false, false],
  ["Delivery date came and went. No update, no email, nothing. Where is it?", true, false, true],
  ["My card was declined at checkout but the order still shows as placed. Was I charged?", false, true, false],
  ["Just a heads-up that the manual has a typo on page 4 (it says 'recieve').", false, false, false],
  ["We were quoted free shipping and then charged $30 for it. Please remove the charge.", false, true, false],
  ["Any chance the shipment could go out sooner? It's not late, we're just eager.", false, false, false],
  ["Second unit in a row that arrived dead on arrival. This is getting old.", false, false, true],
  ["The subscription renewed even though I cancelled in October. I want that money back.", false, true, true],
  ["Slight delay on my end: I'll send the signed contract tomorrow instead of today.", false, false, false],
  ["The courier says the shipment is held at customs and has been for nine days. What do you need from me?", true, false, false],
  ["Thanks for the refund, it came through this morning.", false, true, false],
  ["How long does standard delivery usually take to Portugal?", false, false, false],
  ["You promised the 15th. It's the 22nd. My client is threatening to cancel. What do I tell them?", true, false, true],
  ["Is there a discount for nonprofits? We're a registered charity.", false, true, false],
  ["The shipping notification arrived but the tracking number doesn't work on the carrier's site.", false, false, false],
  ["Whatever, I'll just buy from a competitor. Don't bother replying.", false, false, true],
  ["Receipt shows the wrong company name. Can you reissue it under 'Globex Ltd'?", false, true, false],
  ["Delivered on time, but to my old address. My mistake, I forgot to update it.", false, false, false],
  ["Late again. Every single month the invoice is late and then you charge a late fee. Unbelievable.", false, true, true],
  ["Two of the three boxes arrived Monday; the third is still in transit with no ETA.", true, false, false],
  ["Loving the product. When do you plan to add dark mode?", false, false, false],
  ["The driver marked it delivered at 2:14pm. I was home. Nothing came. This is theft as far as I'm concerned.", true, false, true],
  ["Could I get an itemized bill for last month? Finance wants a breakdown.", false, true, false],
  ["Shipping was fast, packaging was terrible. The item survived but only just.", false, false, false],
  ["I need the order by Friday or the whole project slips. Can you expedite?", false, false, false],
  ["Still waiting on the credit note you promised two weeks ago.", false, true, false],
  ["Frankly your support is useless. Six emails, zero answers.", false, false, true],
  ["The parcel was due yesterday; tracking hasn't moved since it left the depot on Sunday.", true, false, false],
  ["Please add a purchase order number to future invoices: PO-77812.", false, true, false],
  ["Arrived on schedule, no issues. You can close the ticket.", false, false, false],
  ["Why was I charged a restocking fee for a return you told me was free?", false, true, true],
  ["Any update on the backorder? The site said 'ships in 3-5 days' when I ordered a month ago.", true, false, false],
  ["Can I pay the annual invoice in two installments?", false, true, false],
  ["The product is fine. The wait was not. Twenty-six days for a 'two-day' shipment.", true, false, true],
  ["Small thing: the tracking email went to my spam folder. Might be worth checking your DKIM.", false, false, false],
  ["The order shows as shipped but I never got a tracking number.", false, false, false],
  ["You have exactly one day to sort out this refund before I leave reviews everywhere.", false, true, true],
  ["Got the parcel, thanks. Slightly later than hoped but no complaints.", true, false, false],
  ["Please put the account on hold for two months, we're between projects.", false, false, false],
  ["The quote says net 30 but the invoice says due on receipt. Which applies?", false, true, false],
  ["Delayed shipment, damaged goods, and now a surprise customs bill. What a week.", true, true, true],
  ["Fantastic, the express upgrade got it here in a day. Worth every cent.", false, false, false],
  ["I'm not angry, just confused: why do I have two active subscriptions?", false, true, false],
  ["Nothing is late, nothing is broken. I just want to change the delivery address for next month.", false, false, false],
  ["When exactly will the shipment leave the warehouse? The status has said 'processing' for a week.", true, false, false],
];

export const messages: LabeledMessage[] = rows.map(([text, delay, billing, angry], index) => ({
  id: `m${String(index + 1).padStart(3, "0")}`,
  text,
  delay,
  billing,
  angry,
}));

export const predicates = {
  delay: "mentions a shipping delay: a shipment, delivery, or order that is late, delayed, or has not arrived when expected",
  billing: "is about billing or payment: charges, invoices, refunds, prices, or subscription cost",
  angry: "expresses anger, hostility, or clear frustration toward the company",
} as const;

export type PredicateName = keyof typeof predicates;
