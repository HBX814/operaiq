import { getApps, initializeApp } from "firebase-admin/app"
import { getFirestore } from "firebase-admin/firestore"
import { NextResponse } from "next/server"

if (!getApps().length) {
  initializeApp()
}

export async function GET() {
  try {
    const db = getFirestore()
    const snap = await db.collection("postmortems").get()
    if (snap.empty) return NextResponse.json([])
    const docs = snap.docs.map(doc => {
      const data = doc.data();
      return {
        id: doc.id,
        ...data,
        created_at: 
          data.created_at?.toDate?.()?.toISOString() || 
          data.created_at || 
          new Date().toISOString(),
      };
    })
    return NextResponse.json(docs)
  } catch (err: any) {
    console.error("Firestore postmortems error:", err)
    return NextResponse.json(
      { error: err.message || String(err) },
      { status: 500 }
    )
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { postmortem_id, ...data } = body;
    
    if (!postmortem_id) {
        return NextResponse.json({ error: "postmortem_id required" }, { status: 400 });
    }

    const db = getFirestore();
    await db.collection("postmortems").doc(postmortem_id).set({
      ...data,
      updated_at: new Date().toISOString()
    }, { merge: true });

    return NextResponse.json({ status: "success", postmortem_id });
  } catch (error: any) {
    console.error("Error updating postmortem:", error);
    return NextResponse.json({
      error: error.message || String(error)
    }, { status: 500 });
  }
}
